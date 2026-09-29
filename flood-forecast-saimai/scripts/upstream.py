#!/usr/bin/env python3
"""ต้นน้ำของเขื่อน + โครงข่ายลุ่มเจ้าพระยาทั้งระบบ จาก HydroRIVERS -> data/geo/upstream.json

ตอบคำถาม "น้ำที่เข้าเขื่อนมาจากไหน": ไล่ย้อน NEXT_DOWN จากช่วงลำน้ำที่ตัวเขื่อนตั้งอยู่ขึ้นไป
ได้ทุกลำน้ำที่ไหลลงอ่าง แล้วต่อช่วงสั้นๆ (~5 กม.) เป็นสายยาวเรียงตามทิศการไหล ไว้วาดลูกศร
พร้อมหาอำเภอที่ลำน้ำสายหลัก (พื้นที่รับน้ำ ≥ MAJOR_UP) ไหลผ่าน เพื่อกรองธงภัยต้นน้ำ

ต้องรัน hydro_prep.py ก่อน (สร้าง data/geo/hydro_th.json)"""
import json, os, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = {int(k): v for k, v in json.load(open(os.path.join(BASE, "data", "geo", "hydro_th.json"))).items()}
GEO = json.load(open(os.path.join(BASE, "data", "geo", "districts.json")))
DAMS = [d for d in json.load(open(os.path.join(BASE, "data", "dams_verified.json")))["dams"] if d["lat"]]
OUT = os.path.join(BASE, "data", "geo", "upstream.json")

CPY_OUTLET = 41337891          # ช่วงปากแม่น้ำเจ้าพระยาใน HydroRIVERS (พื้นที่รับน้ำ ~144,000 km²)
MAJOR_UP = 1000                # km² ลำน้ำที่นับว่า "สายหลัก" ใช้หาอำเภอ/ธงต้นน้ำ
BASIN_MIN_UP = 800             # km² ความละเอียดของภาพลุ่มเจ้าพระยาทั้งระบบ

ups = {}
for k, v in S.items():
    ups.setdefault(v["dn"], []).append(k)


def km(a, b):
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0]))) * 111.2


def dam_segment(lat, lon, r=4.0):
    """ช่วงลำน้ำที่ผ่านตัวเขื่อน = ช่วงที่มีพื้นที่รับน้ำมากสุดในรัศมี r กม. (ลำน้ำหลักที่ถูกกั้น)"""
    best = None
    for k, v in S.items():
        g = v["g"]
        if abs(g[0][0] - lat) > 0.3 or abs(g[0][1] - lon) > 0.3:
            continue
        if min(km((lat, lon), p) for p in g) <= r and (best is None or v["up"] > S[best]["up"]):
            best = k
    return best


def tree(root, min_up):
    out, st = [], [root]
    while st:
        k = st.pop()
        out.append(k)
        st += [u for u in ups.get(k, []) if S[u]["up"] >= min_up]
    return out


def chains(ids):
    """ต่อช่วงเป็นสาย: เริ่มจากช่วงที่ไม่มีต้นน้ำในชุด หรือไม่ใช่สาขาใหญ่สุดของช่วงถัดไป แล้วเดินลงจนชนสายที่ใหญ่กว่า"""
    idset = set(ids)
    main_child = {}
    for k in ids:
        dn = S[k]["dn"]
        if dn in idset and (dn not in main_child or S[k]["up"] > S[main_child[dn]]["up"]):
            main_child[dn] = k
    res = []
    for k in ids:
        if main_child.get(S[k]["dn"]) == k and any(main_child.get(k) == u for u in ups.get(k, [])):
            continue  # อยู่กลางสาย ไม่ใช่จุดเริ่ม
        if k in main_child.values() and main_child.get(k):
            continue
        line, cur = [], k
        while True:
            line += S[cur]["g"] if not line else S[cur]["g"][1:]
            dn = S[cur]["dn"]
            if dn not in idset or main_child.get(dn) != cur:
                break
            cur = dn
        res.append({"up": S[cur]["up"], "g": simplify(line)})
    res.sort(key=lambda c: c["up"])
    return res


def simplify(pts, tol=0.004):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        i, j = st.pop()
        (ay, ax), (by, bx) = pts[i], pts[j]
        dy, dx = by - ay, bx - ax
        n2 = dx * dx + dy * dy or 1e-12
        bd, bk = -1, -1
        for k in range(i + 1, j):
            py, px = pts[k]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / n2))
            dd = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if dd > bd:
                bd, bk = dd, k
        if bk > 0 and bd > tol * tol:
            keep[bk] = True
            st += [(i, bk), (bk, j)]
    return [p for p, k in zip(pts, keep) if k]


# ---- point-in-polygon อำเภอ (bbox ก่อน) ----
DB = []
for code, v in GEO.items():
    for ring in v["g"]:
        ys = [p[0] for p in ring]
        xs = [p[1] for p in ring]
        DB.append((min(ys), max(ys), min(xs), max(xs), ring, code))


def pip(y, x, ring):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def district_of(y, x):
    for y0, y1, x0, x1, ring, code in DB:
        if y0 <= y <= y1 and x0 <= x <= x1 and pip(y, x, ring):
            return code
    return None


def districts_along(ids):
    codes = set()
    for k in ids:
        if S[k]["up"] < MAJOR_UP:
            continue
        for p in S[k]["g"][::3] + [S[k]["g"][-1]]:
            c = district_of(*p)
            if c:
                codes.add(c)
    return sorted(codes)


out = {"dams": {}, "basin": None}
for d in DAMS:
    seg = dam_segment(d["lat"], d["lon"])
    if not seg:
        print("WARN ไม่พบลำน้ำที่ตัวเขื่อน", d["name"])
        continue
    area = S[seg]["up"]
    ids = tree(seg, max(80, area * 0.01))
    # เขื่อนอื่นที่อยู่ต้นน้ำ (ตั้งอยู่บนช่วงในต้นไม้นี้)
    idset = set(ids)
    up_dams = [o["name"] for o in DAMS if o["name"] != d["name"] and dam_segment(o["lat"], o["lon"], 3) in idset]
    out["dams"][d["name"]] = {"seg": seg, "area_km2": area, "chains": chains(ids),
                              "codes": districts_along(ids), "up_dams": up_dams}
    print(f"  {d['name']}: พื้นที่รับน้ำ {area:,} km² ช่วง {len(ids)} สาย {len(out['dams'][d['name']]['chains'])} "
          f"อำเภอ {len(out['dams'][d['name']]['codes'])} เขื่อนต้นน้ำ {up_dams}")

bids = tree(CPY_OUTLET, BASIN_MIN_UP)
bset = set(tree(CPY_OUTLET, 50))
basin_dams = [n for n, v in out["dams"].items() if v["seg"] in bset]
out["basin"] = {"name": "ลุ่มเจ้าพระยา", "area_km2": S[CPY_OUTLET]["up"], "chains": chains(bids),
                "codes": districts_along(bids), "dams": basin_dams}
print("  basin dams:", basin_dams)
print(f"  basin CPY: ช่วง {len(bids)} สาย {len(out['basin']['chains'])} อำเภอ {len(out['basin']['codes'])}")

json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print(f"OK {OUT} size={os.path.getsize(OUT) / 1e3:.0f} KB")
