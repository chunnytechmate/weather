#!/usr/bin/env python3
"""หาสถานีวัดระดับน้ำใกล้ สายไหม ซอย 44 จากข้อมูล thaiwater waterlevel_load"""
import json, math, sys

DATA = "data/thaiwater_waterlevel_20260927.json"
# จุดอ้างอิง: กลางเขตสายไหมฝั่งตะวันออก (ใกล้ท้ายซอยสายไหม 44)
REF_LAT, REF_LON = 13.912, 100.672

def km(lat, lon):
    return math.hypot((float(lat) - REF_LAT) * 111.0, (float(lon) - REF_LON) * 111.0 * math.cos(math.radians(REF_LAT)))

d = json.load(open(DATA))
rows = []
for s in d["waterlevel_data"]["data"]:
    st = s.get("station") or {}
    lat, lon = st.get("tele_station_lat"), st.get("tele_station_long")
    if lat is None or lon is None:
        continue
    name = (st.get("tele_station_name") or {}).get("th", "")
    rows.append({
        "dist": km(lat, lon),
        "name": name,
        "river": s.get("river_name") or "",
        "msl": s.get("waterlevel_msl"),
        "prev": s.get("waterlevel_msl_previous"),
        "flow": s.get("flow_rate"),
        "bank_min": st.get("min_bank"),
        "ground": st.get("ground_level"),
        "warn": st.get("warning_level_m"),
        "crit": st.get("critical_level_m"),
        "dt": s.get("waterlevel_datetime"),
        "sit": s.get("situation_level"),
        "agency": ((s.get("agency") or {}).get("agency_shortname") or {}).get("th", ""),
    })

rows.sort(key=lambda r: r["dist"])
print(f"{'dist_km':>6} | {'สถานี':<28} | {'ลำน้ำ':<16} | msl | prev | bank | flow | เวลา")
for r in rows[:25]:
    print(f"{r['dist']:6.1f} | {r['name'][:28]:<28} | {str(r['river'])[:16]:<16} | {r['msl']} | {r['prev']} | {r['bank_min']} | {r['flow']} | {r['dt']}")

print("\n-- สถานีเจ้าพระยาฝั่งกรุงเทพฯ (ชื่อมีคำเหล่านี้) --")
for r in rows:
    if r["dist"] < 60 and any(k in r["river"] for k in ("เจ้าพระยา",)) :
        print(f"{r['dist']:6.1f} | {r['name'][:28]:<28} | {str(r['river'])[:16]:<16} | {r['msl']} | {r['prev']} | bank {r['bank_min']} | warn {r['warn']} | {r['dt']}")
