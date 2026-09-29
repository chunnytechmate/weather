#!/usr/bin/env python3
"""ตัด HydroRIVERS v10 (เอเชีย) เฉพาะไทยและลุ่มที่ไหลเข้าไทย -> data/geo/hydro_th.json

HydroRIVERS (HydroSHEDS, Lehner & Grill 2013) คือโครงข่ายแม่น้ำที่ทุกช่วงรู้ "ช่วงถัดไปทางท้ายน้ำ"
(NEXT_DOWN) และพื้นที่รับน้ำสะสม (UPLAND_SKM) จึงไล่ต้นน้ำของเขื่อนได้ทั้งต้นไม้โดยไม่ต้องเดาทิศ
(แนวคิดเดียวกับแผนที่ meanam.com ซึ่งใช้ HydroRIVERS + OSM + ThaiWater)

ดาวน์โหลดครั้งเดียว ~90 MB: https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_as_shp.zip
แตกไว้ที่ data/geo/hydrorivers/ (gitignore) · ใบอนุญาต: HydroSHEDS license (ใช้ได้ ต้องอ้างอิงที่มา)
อ่าน .shp/.dbf เองด้วย struct ไม่ต้องลง library เพิ่ม"""
import json, os, struct

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "data", "geo", "hydrorivers", "HydroRIVERS_v10_as_shp", "HydroRIVERS_v10_as")
OUT = os.path.join(BASE, "data", "geo", "hydro_th.json")
BBOX = (5.4, 96.8, 21.2, 106.2)   # lat0, lon0, lat1, lon1 (รวมต้นน้ำโขง/สาละวินฝั่งพม่า-ลาวที่ติดไทย)
MIN_UPLAND = 50                    # km² ตัดลำห้วยเล็กมากทิ้ง


def dbf_rows(path):
    f = open(path, "rb")
    n, hl, rl = struct.unpack("<IHH", f.read(32)[4:12])
    fields = []
    while True:
        d = f.read(32)
        if d[0] == 0x0D:
            break
        fields.append((d[:11].split(b"\0")[0].decode(), d[16]))
    f.seek(hl)
    for _ in range(n):
        rec = f.read(rl)
        pos, row = 1, {}
        for name, ln in fields:
            v = rec[pos:pos + ln].strip()
            pos += ln
            row[name] = float(v) if v else None
        yield row


def shp_lines(path):
    f = open(path, "rb")
    f.seek(100)
    while True:
        h = f.read(8)
        if len(h) < 8:
            return
        _, clen = struct.unpack(">ii", h)
        body = f.read(clen * 2)
        st = struct.unpack("<i", body[:4])[0]
        if st != 3:
            yield None
            continue
        xmin, ymin, xmax, ymax = struct.unpack("<4d", body[4:36])
        nparts, npts = struct.unpack("<ii", body[36:44])
        pts = struct.unpack(f"<{npts * 2}d", body[44 + 4 * nparts:44 + 4 * nparts + 16 * npts])
        yield (ymin, xmin, ymax, xmax), [(pts[i + 1], pts[i]) for i in range(0, len(pts), 2)]


segs = {}
for row, shp in zip(dbf_rows(SRC + ".dbf"), shp_lines(SRC + ".shp")):
    if shp is None:
        continue
    (y0, x0, y1, x1), pts = shp
    if y1 < BBOX[0] or y0 > BBOX[2] or x1 < BBOX[1] or x0 > BBOX[3]:
        continue
    if (row["UPLAND_SKM"] or 0) < MIN_UPLAND:
        continue
    segs[int(row["HYRIV_ID"])] = {
        "dn": int(row["NEXT_DOWN"]), "main": int(row["MAIN_RIV"]), "up": round(row["UPLAND_SKM"]),
        "q": row["DIS_AV_CMS"], "ord": int(row["ORD_CLAS"]), "km": row["LENGTH_KM"],
        "g": [[round(a, 4), round(b, 4)] for a, b in pts]}

json.dump(segs, open(OUT, "w"), separators=(",", ":"))
print(f"OK {OUT} segments={len(segs)} size={os.path.getsize(OUT) / 1e6:.1f} MB")
