#!/usr/bin/env python3
"""เตรียมขอบเขตอำเภอทั้งประเทศ (928 อำเภอ) สำหรับ highlight บนแผนที่เขื่อน

ต้นทาง: github.com/chingchai/OpenGISData-Thailand (districts.geojson, ข้อมูลกรมการปกครอง)
ย่อรูปด้วย Douglas-Peucker (~300 ม.) แล้วปัดทศนิยม 4 ตำแหน่ง เขียน data/geo/districts.json
รันครั้งเดียวพอ (ขอบเขตอำเภอไม่ค่อยเปลี่ยน) และตรวจว่าชื่ออำเภอใน dam_zones.py มีจริงทุกชื่อ"""
import json, os, sys, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from dam_zones import all_districts

SRC = "https://raw.githubusercontent.com/chingchai/OpenGISData-Thailand/master/districts.geojson"
RAW = os.path.join(BASE, "data", "geo", "raw_districts.geojson")
OUT = os.path.join(BASE, "data", "geo", "districts.json")
TOL = 0.003  # องศา ~300 ม. พอสำหรับซูมระดับจังหวัด
FIX_NAME = {"เมืองสุราษฎร์ธาน": "เมืองสุราษฎร์ธานี"}  # ชื่อพิมพ์ตกในไฟล์ต้นทาง


def dp(pts, tol):
    """Douglas-Peucker แบบ iterative (ring ยาวหลักหมื่นจุด recursion ลึกเกิน)"""
    if len(pts) < 5:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        n2 = dx * dx + dy * dy
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if n2 == 0:
                d = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / n2))
                d = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d > best:
                best, idx = d, i
        if idx > 0 and best > tol * tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


if not os.path.exists(RAW):
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    print("download", SRC)
    urllib.request.urlretrieve(SRC, RAW)

gj = json.load(open(RAW))
out = {}
for f in gj["features"]:
    p = f["properties"]
    polys = []
    for poly in f["geometry"]["coordinates"]:
        ring = dp([(x, y) for x, y, *_ in poly[0]], TOL)  # เอาเฉพาะวงนอก รูในอำเภอไม่มีผลกับ highlight
        if len(ring) >= 4:
            polys.append([[round(y, 4), round(x, 4)] for x, y in ring])  # Leaflet ใช้ [lat, lon]
    out[p["amp_code"]] = {"p": p["pro_th"], "a": FIX_NAME.get(p["amp_th"], p["amp_th"]), "g": polys}

json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print(f"OK {OUT} districts={len(out)} size={os.path.getsize(OUT)/1e6:.2f} MB")

have = {(v["p"], v["a"]) for v in out.values()}
missing = sorted(all_districts() - have)
if missing:
    raise SystemExit(f"ชื่ออำเภอใน dam_zones.py ไม่ตรงกับ geojson: {missing}")
print("dam_zones: ชื่ออำเภอครบทุกชื่อ", len(all_districts()))
