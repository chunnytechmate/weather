#!/usr/bin/env python3
"""ธงภัยริมแม่น้ำ: สถานีวัดระดับน้ำโทรมาตรทั่วประเทศ (~800 สถานี) -> data/river_flags.json

ธงปักที่สถานีริมแม่น้ำ ไม่ใช่ที่เขื่อน เพราะจุดที่น้ำล้นตลิ่งจริงคือลำน้ำท้ายเขื่อน
(หลายจุดไม่มีเขื่อนอยู่ใกล้เลย เช่น C.2 นครสวรรค์, บางไทร อยุธยา)

แหล่ง: api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load (สสน. รวม RID/HII/EGAT/กองทัพเรือ)
สีธงใช้ situation_level ของ thaiwater เอง (เทียบระดับน้ำกับตลิ่งต่ำสุด min_bank):
  1-3 = ≤ 70% ของความลึกตลิ่ง  -> เขียว ปกติ
  4   = 70-100%               -> เหลือง เฝ้าระวัง
  5   = เกินตลิ่ง               -> แดง ล้นตลิ่ง
ข้อมูลเก่ากว่า 24 ชม. ไม่ปักธง (ค้างไม่ได้แปลว่าปลอดภัย)

ประวัติ (ตัวเลื่อนเวลาใน dashboard): data/flag_history.json เก็บ "% ของความลึกตลิ่ง สูงสุดของวัน" รายสถานี
  - รันปกติ (ทุกชั่วโมง): อัปเดตค่าสูงสุดของวันนี้จากค่าอ่านล่าสุด
  - --backfill [วัน]: ดึงย้อนหลังครั้งเดียวจาก waterlevel_graph (ค่าเริ่ม 60 วัน, ~10 นาที)
  % ตลิ่ง = (ระดับ - ท้องน้ำ ground_level) / (ตลิ่ง min_bank - ground_level) x 100 ตรงกับ storage_percent ของ thaiwater"""
import json, os, sys, datetime, urllib.request, time
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "river_flags.json")
HIST = os.path.join(BASE, "data", "flag_history.json")
GRAPH = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_graph"
KEEP_DAYS = 90
URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


req = urllib.request.Request(URL, headers={"User-Agent": "saimai-flood-dashboard/1.0"})
rows = json.load(urllib.request.urlopen(req, timeout=60))["waterlevel_data"]["data"]
now = datetime.datetime.now()
flags, stale = [], 0
for s in rows:
    st = s.get("station") or {}
    lat, lon = fnum(st.get("tele_station_lat")), fnum(st.get("tele_station_long"))
    lvl, msl = s.get("situation_level"), fnum(s.get("waterlevel_msl"))
    if lat is None or lvl is None or msl is None:
        continue
    try:
        dt = datetime.datetime.strptime(s["waterlevel_datetime"], "%Y-%m-%d %H:%M")
    except (KeyError, ValueError):
        continue
    if now - dt > datetime.timedelta(hours=24):
        stale += 1
        continue
    gc = s.get("geocode") or {}
    bank, lb, rb = fnum(st.get("min_bank")), fnum(st.get("left_bank")), fnum(st.get("right_bank"))
    # ธงแดงที่น่าสงสัย: เกิน min_bank แต่ยังต่ำกว่าตลิ่งซ้าย/ขวาที่สำรวจทั้งสองฝั่งเกิน 1 ม.
    # (เช่น บ้านปากแซง min_bank 45.8 แต่ตลิ่ง 96-97 ม.) คงสีตามแหล่งแต่ติดหมายเหตุให้ตรวจ
    suspect = bool(lvl >= 5 and lb is not None and rb is not None and msl < min(lb, rb) - 1)
    prev = fnum(s.get("waterlevel_msl_previous"))
    flags.append({
        "id": st.get("id"), "ground": fnum(st.get("ground_level")),
        "reg": ((gc.get("area_name") or {}).get("th") or ""),
        "name": ((st.get("tele_station_name") or {}).get("th") or "").strip(),
        "code": st.get("tele_station_oldcode") or "", "river": s.get("river_name") or "",
        "lat": lat, "lon": lon, "lb": lb, "rb": rb, "level": int(lvl),
        "sev": 2 if lvl >= 5 else 1 if lvl == 4 else 0,
        "msl": msl, "bank": bank, "pct": fnum(s.get("storage_percent")),
        "trend": round(msl - prev, 2) if prev is not None else None,
        "dt": s["waterlevel_datetime"], "suspect": suspect,
        "agency": ((s.get("agency") or {}).get("agency_shortname") or {}).get("en", ""),
        "pro": (gc.get("province_name") or {}).get("th", ""), "amp": (gc.get("amphoe_name") or {}).get("th", "")})

def bank_pct(v, f):
    if v is None or f["bank"] is None or f["ground"] is None or f["bank"] - f["ground"] <= 0.2:
        return None
    return round((v - f["ground"]) / (f["bank"] - f["ground"]) * 100)


hist = json.load(open(HIST)) if os.path.exists(HIST) else {}
today = now.date().isoformat()
for f in flags:
    if f["id"] is None:
        continue
    h = hist.setdefault(str(f["id"]), {})
    p = f["pct"] if f["pct"] is not None else bank_pct(f["msl"], f)
    if p is not None and f["dt"][:10] == today:
        h[today] = max(h.get(today, -1e9), round(p))


def backfill(f, days):
    """ประวัติรายวันจาก graph: ค่าสูงสุดของวัน แปลง datum ด้วย offset จากค่าอ่านล่าสุด (สถานี RID บางแห่งเป็น gauge)"""
    end = now.date()
    url = (f"{GRAPH}?station_type=tele_waterlevel&station_id={f['id']}"
           f"&start_date={(end - datetime.timedelta(days=days)).isoformat()}&end_date={end.isoformat()}")
    for a in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "saimai-flood-dashboard/1.0"})
            g = json.load(urllib.request.urlopen(req, timeout=90))["data"]["graph_data"]
            break
        except Exception:
            if a == 2:
                return f["id"], None
            time.sleep(3)
    pts = [(p["datetime"], p["value"]) for p in g if p.get("value") is not None]
    if not pts:
        return f["id"], None
    near = min(pts, key=lambda p: abs(datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M") -
                                     datetime.datetime.strptime(f["dt"], "%Y-%m-%d %H:%M")))
    off = f["msl"] - near[1]
    off = 0.0 if abs(off) < 0.3 else off   # ต่างเล็กน้อย = ระดับเปลี่ยนตามเวลา ไม่ใช่ datum ต่าง
    day = {}
    for t, v in pts:
        day[t[:10]] = max(day.get(t[:10], -1e9), v + off)
    return f["id"], {d: bank_pct(v, f) for d, v in day.items() if bank_pct(v, f) is not None}


if "--backfill" in sys.argv:
    i = sys.argv.index("--backfill")
    days = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 60
    todo = [f for f in flags if f["id"] is not None and f["bank"] is not None and f["ground"] is not None]
    print(f"backfill {len(todo)} stations x {days} days", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sid, daily in ex.map(lambda f: backfill(f, days), todo):
            done += 1
            if daily:
                h = hist.setdefault(str(sid), {})
                for d, v in daily.items():
                    h[d] = max(h.get(d, -1e9), v) if d == today else v
            if done % 100 == 0:
                print(f"  {done}/{len(todo)}", flush=True)

cut = (now.date() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
hist = {k: {d: v for d, v in sorted(h.items()) if d >= cut} for k, h in hist.items()}
json.dump(hist, open(HIST, "w"), separators=(",", ":"))

json.dump({"fetched_at": now.isoformat(timespec="seconds"), "source": URL, "flags": flags},
          open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
sev = [f["sev"] for f in flags]
print(f"OK {OUT} flags={len(flags)} red={sev.count(2)} yellow={sev.count(1)} green={sev.count(0)} "
      f"stale_skipped={stale} suspect_bank={sum(f['suspect'] for f in flags)} "
      f"history_stations={len(hist)} days={len({d for h in hist.values() for d in h})}")
