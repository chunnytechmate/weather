#!/usr/bin/env python3
"""ข้อมูลฝึกโมเดลผลกระทบสายไหม/ลำลูกกา: ประวัติรายวันย้อนหลังตั้งแต่ START -> data/impact/

  stations.json  ระดับน้ำรายวัน (ม.รทก. เฉลี่ย/สูงสุดของวัน) สถานีเป้าหมาย + สถานีต้นทาง ~20 แห่ง
                 จาก thaiwater waterlevel_graph (ความละเอียด ~10 นาที ย้อนได้ถึงปี 2566)
  dams.json      % ความจุ ปริมาตร ไหลเข้า ระบาย รายวัน ทุกเขื่อน RID จาก app.rid.go.th (ย้อนรายวันได้)
  rain.json      ฝนรายวันจาก Open-Meteo archive (ERA5) 3 จุด: สายไหม, ลุ่มป่าสัก, เจ้าพระยาตอนล่าง
                 + พยากรณ์ 16 วันจาก Open-Meteo forecast (ใช้เป็นสถานการณ์เสริม ไม่ใช่ตัวหลัก)

รันซ้ำได้: ดึงเฉพาะวันที่ยังไม่มี (ยกเว้น 5 วันล่าสุดดึงซ้ำเสมอ)"""
import json, os, datetime, time, urllib.request, ssl
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(BASE, "data", "impact")
os.makedirs(DIR, exist_ok=True)
START = datetime.date(2023, 6, 1)
TODAY = datetime.date.today()
UA = {"User-Agent": "saimai-flood-dashboard/1.0"}
CTX = ssl.create_default_context()

# id ของ thaiwater (tele_waterlevel) · role: target = เป้าพยากรณ์, driver = ตัวขับต้นทาง
STATIONS = {
    11: ("สายไหม: คลองลาดพร้าว ท้ายปตร.คลอง2", "target"),
    37: ("ลำลูกกา: คลองหกวา คลอง8", "target"),
    8: ("คลองลาดพร้าว ปากคลอง2สายใต้", "local"),
    1: ("คลองลาดพร้าว วัดบางบัว", "local"),
    27: ("คลองเปรมประชากร หลักหก", "local"),
    29: ("คลองระพีพัฒน์แยกตก (คลองหลวง)", "rapipat"),
    36: ("คลองระพีพัฒน์แยกใต้ (หนองเสือ)", "rapipat"),
    2712: ("S.28 ท้ายเขื่อนป่าสักชลสิทธิ์", "pasak"),
    2632: ("S.9 บ้านป่า แก่งคอย", "pasak"),
    2624: ("S.26 ท้ายเขื่อนพระรามหก", "pasak"),
    2607: ("S.5 อยุธยา (ป่าสัก)", "pasak"),
    2795: ("C.2 นครสวรรค์", "cpy"),
    2744: ("C.13 ท้ายเขื่อนเจ้าพระยา", "cpy"),
    58: ("เมืองอ่างทอง", "cpy"),
    2609: ("C.35 บ้านป้อม อยุธยา", "cpy"),
    49: ("บางปะอิน", "cpy"),
    26: ("สะพานนวลฉวี", "cpy"),
    2599: ("C.12 สามเสน", "cpy"),
    4: ("สะพานกรุงเทพ (น้ำทะเลหนุน)", "tide"),
    189: ("องครักษ์ (นครนายก)", "east"),
}
RAIN_PTS = {"saimai": (13.918, 100.651), "pasak": (15.40, 101.15), "cpylow": (14.80, 100.40)}
GRAPH = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_graph"


def get(url, timeout=120):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=CTX) as r:
                return json.load(r)
        except Exception:
            if a == 3:
                raise
            time.sleep(4 * (a + 1))


def load(name, default):
    f = os.path.join(DIR, name)
    return json.load(open(f)) if os.path.exists(f) else default


def save(name, obj):
    json.dump(obj, open(os.path.join(DIR, name), "w"), ensure_ascii=False, separators=(",", ":"))


recent_cut = (TODAY - datetime.timedelta(days=5)).isoformat()

# ---------- สถานี: ดึงเป็นช่วง 90 วัน ----------
st_data = load("stations.json", {})


def windows():
    d = START
    while d <= TODAY:
        e = min(TODAY, d + datetime.timedelta(days=89))
        yield d, e
        d = e + datetime.timedelta(days=1)


def fetch_station(sid):
    have = st_data.get(str(sid), {}).get("daily", {})
    out = dict(have)
    for a, b in windows():
        if b.isoformat() < recent_cut and all((a + datetime.timedelta(days=i)).isoformat() in have
                                              for i in range(0, (b - a).days + 1, 7)):
            continue
        try:
            g = get(f"{GRAPH}?station_type=tele_waterlevel&station_id={sid}&start_date={a}&end_date={b}")["data"]["graph_data"]
        except Exception as e:
            print("  WARN", sid, a, e, flush=True)
            continue
        day = {}
        for p in g:
            if p.get("value") is None:
                continue
            day.setdefault(p["datetime"][:10], []).append(float(p["value"]))
        for d, v in day.items():
            if len(v) >= 12:   # อย่างน้อย ~2 ชม. ของข้อมูล 10 นาที (สถานี RID รายชั่วโมง = 12 ชม.)
                out[d] = [round(sum(v) / len(v), 3), round(max(v), 3), len(v)]
    return sid, out


with ThreadPoolExecutor(max_workers=5) as ex:
    for sid, daily in ex.map(fetch_station, STATIONS):
        st_data[str(sid)] = {"name": STATIONS[sid][0], "role": STATIONS[sid][1], "daily": dict(sorted(daily.items()))}
        print(f"  station {sid} {STATIONS[sid][0]}: {len(daily)} วัน", flush=True)
save("stations.json", st_data)

# ---------- เขื่อน RID รายวัน ----------
dams = load("dams.json", {})


def fetch_dam_day(d):
    try:
        r = get(f"https://app.rid.go.th/reservoir/api/dam/public/{d}", timeout=40)
        if r.get("date") != d:
            return d, None
        rows = {}
        for reg in r.get("data", []):
            for x in reg.get("dam", []):
                rows[x["name"].replace("เขื่อน", "").strip()] = [x.get("percent_storage"), x.get("volume"),
                                                                 x.get("inflow"), x.get("outflow"), x.get("storage")]
        return d, rows
    except Exception:
        return d, None


need = [(START + datetime.timedelta(days=i)).isoformat() for i in range((TODAY - START).days + 1)]
need = [d for d in need if d not in dams or d >= recent_cut]
with ThreadPoolExecutor(max_workers=8) as ex:
    for d, rows in ex.map(fetch_dam_day, need):
        if rows:
            dams[d] = rows
save("dams.json", dict(sorted(dams.items())))
print(f"  dams: {len(dams)} วัน", flush=True)

# ---------- ฝน ----------
rain = {"obs": {}, "fc": {}}
for k, (lat, lon) in RAIN_PTS.items():
    a = get(f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
            f"&start_date={START}&end_date={TODAY}&daily=precipitation_sum&timezone=Asia%2FBangkok")["daily"]
    obs = {t: p for t, p in zip(a["time"], a["precipitation_sum"]) if p is not None}
    f = get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&daily=precipitation_sum&past_days=10&forecast_days=16&timezone=Asia%2FBangkok")["daily"]
    for t, p in zip(f["time"], f["precipitation_sum"]):
        if p is None:
            continue
        if t <= TODAY.isoformat():
            obs.setdefault(t, p)   # archive ช้า ~5 วัน เติมด้วยค่าที่ forecast API รายงานย้อนหลัง
        else:
            rain["fc"].setdefault(k, {})[t] = p
    rain["obs"][k] = dict(sorted(obs.items()))
save("rain.json", rain)

# ---------- ฝนรายจังหวัดตามลำน้ำ (ย้อน 14 วัน + พยากรณ์ 16 วัน) ใช้ใน north-water.html ----------
PROV = [("เชียงใหม่", "ปิงบน", 18.79, 98.98), ("ตาก", "ปิงใต้ภูมิพล", 16.88, 99.13), ("กำแพงเพชร", "ปิง", 16.48, 99.52),
        ("ลำปาง", "วัง", 18.29, 99.49), ("แพร่", "ยมบน", 18.14, 100.14), ("สุโขทัย", "ยม", 17.01, 99.82),
        ("น่าน", "น่านบน", 18.78, 100.78), ("อุตรดิตถ์", "น่าน", 17.62, 100.10), ("พิษณุโลก", "น่าน/ยม", 16.82, 100.26),
        ("พิจิตร", "น่าน/ยม", 16.44, 100.35), ("นครสวรรค์", "C.2", 15.70, 100.14), ("ชัยนาท", "เขื่อนเจ้าพระยา", 15.19, 100.13),
        ("เพชรบูรณ์", "ป่าสักบน", 16.42, 101.16), ("ลพบุรี", "ป่าสัก", 14.80, 100.65), ("อยุธยา", "เจ้าพระยา/ป่าสัก", 14.35, 100.57),
        ("ปทุมธานี", "ลำลูกกา", 13.99, 100.68), ("สายไหม", "กทม.", 13.918, 100.651)]
lat = ",".join(str(p[2]) for p in PROV)
lon = ",".join(str(p[3]) for p in PROV)
r = get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&daily=precipitation_sum&past_days=14&forecast_days=16&timezone=Asia%2FBangkok")
provs = []
for (name, river, la, lo), x in zip(PROV, r):
    provs.append({"name": name, "river": river, "lat": la, "lon": lo,
                  "daily": {t: (v or 0) for t, v in zip(x["daily"]["time"], x["daily"]["precipitation_sum"])}})
save("rain_provinces.json", {"today": TODAY.isoformat(), "provinces": provs})
print(f"  rain_provinces: {len(provs)} จังหวัด")
print(f"  rain: {', '.join(f'{k}={len(v)}' for k, v in rain['obs'].items())} วัน · forecast {len(rain['fc'].get('saimai', {}))} วัน")
print("OK", DIR)
