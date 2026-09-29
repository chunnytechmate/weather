#!/usr/bin/env python3
"""ดึง snapshot ครบสายน้ำ: ต้นน้ำภาคเหนือ -> เขื่อน -> เจ้าพระยา -> คลองพื้นที่ -> ปากน้ำ
   + เซ็นเซอร์คลอง/ถนน กทม. รอบซอย + ฝนซอย + ฝนภาคเหนือ -> data/snapshots/"""
import json, urllib.request, datetime, os, math, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(BASE, "data", "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)
TODAY = datetime.date.today().isoformat()
HOME_LAT, HOME_LON = 13.9175, 100.6512

CHAIN = {
    "headwater": ["เชียงดาว", "สะพานนวรัฐ", "อ.เมืองน่าน", "เมืองแพร่", "สวรรคโลก",
                  "วัดเกยไชยเหนือ", "ชุมแสงสงคราม"],
    "upstream": ["สะพานเดชาติวงศ์", "ค่ายจิรประวัติ", "สะพานธรรมจักร", "ท้ายเขื่อนเจ้าพระยา",
                 "สรรพยา", "พรหมบุรี", "เมืองอ่างทอง", "บ้านบางแก้ว", "พระนครศรีอยุธยา",
                 "บ้านป้อม", "บางปะอิน"],
    "city": ["กรมชลประทานสามเสน", "สะพานกรุงเทพ", "สะพานนวลฉวี"],
    "local": ["คลองลาดพร้าว ปากคลอง2สายใต้", "คลองลาดพร้าว ท้ายปตร.คลอง2",
              "คลองเปรมประชากร หลักหก", "คลองหกวา ลำลูกกา คลอง8"],
    "rapipat": ["คลองระพีพัฒน์แยกตก", "คลองระพีพัฒน์แยกใต้"],
    "sea": ["ปากคลองพระองค์เจ้า", "คลองลัดบางยอ 1"],
}
WANT = {n: grp for grp, names in CHAIN.items() for n in names}
DAMS = ("ภูมิพล", "สิริกิติ์", "กิ่วลม", "บอระเพ็ด")
NORTH_RAIN = [("เชียงใหม่", 18.79, 98.98), ("น่าน", 18.78, 100.78),
              ("สุโขทัย", 17.00, 99.80), ("นครสวรรค์", 15.69, 100.13)]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "saimai-flood-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def km(lat, lon):
    try:
        return math.hypist if False else math.hypot((float(lat) - HOME_LAT) * 111,
                                                    (float(lon) - HOME_LON) * 111 * math.cos(math.radians(HOME_LAT)))
    except (TypeError, ValueError):
        return 9e9

now = datetime.datetime.now().strftime("%Y%m%d-%H%M")

stations = []
for s in get("https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load")["waterlevel_data"]["data"]:
    st = s.get("station") or {}
    name = (st.get("tele_station_name") or {}).get("th", "")
    matched = next((n for n in WANT if n in name), None)
    if not matched:
        continue
    try:
        msl = float(s.get("waterlevel_msl"))
    except (TypeError, ValueError):
        continue
    try:
        prev = float(s.get("waterlevel_msl_previous"))
    except (TypeError, ValueError):
        prev = None
    try:
        bank = float(st.get("min_bank"))
    except (TypeError, ValueError):
        bank = None
    stations.append({"name": name.strip(), "key": matched, "group": WANT[matched],
                     "river": str(s.get("river_name") or ""), "msl": msl, "prev": prev,
                     "bank": bank, "dt": s.get("waterlevel_datetime"),
                     "lat": st.get("tele_station_lat"), "lon": st.get("tele_station_long")})

dams, dams_all = [], []
try:
    dd = get("https://api-v3.thaiwater.net/api/v1/thaiwater30/analyst/dam")["data"]
    # เก็บเขื่อนใหญ่ทั้งประเทศ (dam_daily ~39 แห่ง) ไว้สะสมประวัติสำหรับ fit โมเดล
    # ไม่ผ่าน filter DAMS — ใช้ค้นสถานการณ์ลุ่มน้ำอื่นนอกเจ้าพระยา
    for x in dd.get("dam_daily", []):
        dmeta = x.get("dam") or {}
        pct = x.get("dam_storage_percent")
        if pct is None:
            continue
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        dams_all.append({"name": (dmeta.get("dam_name") or {}).get("th", ""),
                         "agency": ((x.get("agency") or {}).get("agency_shortname") or {}).get("en", ""),
                         "basin": ((x.get("basin") or {}).get("basin_name") or {}).get("th", ""),
                         "province": ((x.get("geocode") or {}).get("province_name") or {}).get("th", ""),
                         "level_m": x.get("dam_level"),
                         "storage_mcm": x.get("dam_storage"), "storage_pct": pct,
                         "max_storage_mcm": dmeta.get("max_storage"),
                         "normal_storage_mcm": dmeta.get("normal_storage"),
                         "inflow": x.get("dam_inflow"), "released": x.get("dam_uses_water"),
                         "released_mcm": x.get("dam_released"),
                         "spill": x.get("dam_spilled"), "date": x.get("dam_date"),
                         "lat": dmeta.get("dam_lat"), "lon": dmeta.get("dam_long")})
    # dedupe ชื่อซ้ำ (บางเขื่อนมีทั้ง record วันนี้+เมื่อวาน) เก็บ record วันที่ล่าสุด
    _latest = {}
    for d in dams_all:
        k = d["name"]
        if k not in _latest or str(d["date"] or "") > str(_latest[k]["date"] or ""):
            _latest[k] = d
    dams_all = sorted(_latest.values(), key=lambda d: -d["storage_pct"])
    for sec in ("dam_daily", "dam_medium", "dam_hourly"):
        for x in dd.get(sec, []):
            dmeta = x.get("dam") or {}
            nm = (dmeta.get("dam_name") or {}).get("th", "")
            if not any(k in nm for k in DAMS):
                continue
            pct = x.get("dam_storage_percent")
            if pct is None:
                continue
            dams.append({"name": nm, "storage_mcm": x.get("dam_storage"),
                         "storage_pct": float(pct), "inflow": x.get("dam_inflow"),
                         "released": x.get("dam_uses_water"),
                         "released_daily": x.get("dam_released"),
                         "spill": x.get("dam_spilled"),
                         "date": x.get("dam_date"), "lat": dmeta.get("dam_lat"),
                         "lon": dmeta.get("dam_long"), "src": sec})
    seen = set()
    dams = [d for d in dams if not (d["name"] in seen or seen.add(d["name"]))]
    dams.sort(key=lambda d: -d["storage_pct"])
except Exception as e:
    print("WARN dam:", e)

canals, roads = [], []
try:
    for s in get("https://api-v3.thaiwater.net/api/v1/thaiwater30/public/canal_waterlevel")["data"]:
        st = s.get("station") or {}
        lat, lon = st.get("canal_lat"), st.get("canal_long")
        d = km(lat, lon)
        dt = str(s.get("canal_datetime") or "")
        if d > 7.5 or not dt.startswith(TODAY):
            continue
        canals.append({"name": ((st.get("canal_name") or {}).get("th") or "").strip(),
                       "value": s.get("canal_value"), "warn": st.get("warning_level"),
                       "crit": st.get("critical_level"), "dt": dt, "lat": lat, "lon": lon,
                       "dist_km": round(d, 1)})
    canals.sort(key=lambda c: c["dist_km"])
except Exception as e:
    print("WARN canal:", e)
try:
    for s in get("https://api-v3.thaiwater.net/api/v1/thaiwater30/public/flood_road")["data"]:
        st = s.get("station") or {}
        lat, lon = st.get("floodroad_lat"), st.get("floodroad_long")
        d = km(lat, lon)
        dt = str(s.get("floodroad_datetime") or "")
        if d > 7.5 or not dt.startswith(TODAY):
            continue
        roads.append({"name": ((st.get("floodroad_name") or {}).get("th") or "").strip(),
                      "cm": s.get("floodroad_value"), "dt": dt, "lat": lat, "lon": lon,
                      "dist_km": round(d, 1)})
    roads.sort(key=lambda r: r["dist_km"])
except Exception as e:
    print("WARN road:", e)

wx = get("https://api.open-meteo.com/v1/forecast?latitude=13.918&longitude=100.651"
         "&hourly=precipitation&daily=precipitation_sum,precipitation_probability_max"
         "&past_days=60&forecast_days=16&timezone=Asia%2FBangkok")

wx_north = []
for nm, lat, lon in NORTH_RAIN:
    for attempt in range(3):
        try:
            w = get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                    "&daily=precipitation_sum&past_days=60&forecast_days=16&timezone=Asia%2FBangkok")
            wx_north.append({"name": nm, "time": w["daily"]["time"],
                             "precip": w["daily"]["precipitation_sum"]})
            break
        except Exception as e:
            if attempt == 2:
                print("WARN wx_north", nm, e)
            time.sleep(3)

# Seasonal (ECMWF SEAS5) สำหรับ forecast เกิน 16 วัน — เก็บ 92 วันให้ครบ horizon ใหม่
def _seasonal(lat, lon):
    w = get("https://seasonal-api.open-meteo.com/v1/seasonal"
            f"?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=Asia%2FBangkok")
    return {"time": w["daily"]["time"][:92], "precip": w["daily"]["precipitation_sum"][:92]}

wx_seasonal = {}
try:
    wx_seasonal["soi"] = _seasonal(13.9175, 100.6512)
    wx_seasonal["north"] = []
    for nm, lat, lon in NORTH_RAIN:
        try:
            wx_seasonal["north"].append({"name": nm, **_seasonal(lat, lon)})
        except Exception as e:
            print("WARN seasonal north", nm, e)
except Exception as e:
    print("WARN seasonal soi:", e)

snap = {"fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "stations": stations, "dams": dams, "dams_all": dams_all,
        "canals": canals, "roads": roads,
        "wx_daily": wx.get("daily"), "wx_hourly_time": wx["hourly"]["time"],
        "wx_hourly_precip": wx["hourly"]["precipitation"], "wx_north": wx_north,
        "wx_seasonal": wx_seasonal}

out = os.path.join(SNAP_DIR, f"snapshot-{now}.json")
json.dump(snap, open(out, "w"), ensure_ascii=False)
print(f"OK {out}")
print(f"  stations={len(stations)} (headwater={sum(1 for s in stations if s['group']=='headwater')}, "
      f"rapipat={sum(1 for s in stations if s['group']=='rapipat')}) dams={len(dams)} "
      f"dams_all={len(dams_all)} canals={len(canals)} roads={len(roads)} wx_north={len(wx_north)}")
missing = set(WANT) - {s["key"] for s in stations}
if missing:
    print("  WARN missing stations:", missing)

# รีเฟรช "ระดับน้ำปกติ" (ประวัติย้อนหลัง 60 วัน) เมื่อไฟล์อายุเกิน 24 ชม.
import subprocess, sys
nl = os.path.join(BASE, "data", "normal_levels.json")
if not os.path.exists(nl) or time.time() - os.path.getmtime(nl) > 24 * 3600:
    try:
        subprocess.run([sys.executable, os.path.join(BASE, "scripts", "normal_levels.py")],
                       timeout=900, check=False)
    except Exception as e:
        print("WARN normal_levels refresh:", e)
