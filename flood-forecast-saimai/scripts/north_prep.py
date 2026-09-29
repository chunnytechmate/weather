#!/usr/bin/env python3
"""เส้นแม่น้ำลุ่มเจ้าพระยาแยกตามสาย (ปิง วัง ยม น่าน ป่าสัก เจ้าพระยา) -> data/geo/north_rivers.json
ใช้วาดแอนิเมชัน north-water.html · ต้องมี data/geo/hydro_th.json (hydro_prep.py) · รันครั้งเดียว

แยกสายจาก HydroRIVERS: ไล่ NEXT_DOWN ของแต่ละช่วงลงไปจนเจอ "จุดออก" ของสายไหนก่อน
(วังไหลลงปิง ยมไหลลงน่าน จึงเช็กวัง/ยมก่อน) ช่วงที่ไม่เข้าสายใด = แม่น้ำเจ้าพระยาสายหลัก"""
import json, os, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = {int(k): v for k, v in json.load(open(os.path.join(BASE, "data", "geo", "hydro_th.json"))).items()}
OUT = os.path.join(BASE, "data", "geo", "north_rivers.json")
CPY_OUTLET = 41337891
MIN_UP = 1500

ups = {}
for k, v in S.items():
    ups.setdefault(v["dn"], []).append(k)
basin, st = [], [CPY_OUTLET]
while st:
    k = st.pop()
    basin.append(k)
    st += [u for u in ups.get(k, []) if S[u]["up"] >= MIN_UP]
bset = set(basin)

# หาจุดออกของแต่ละสาย: เริ่มจากเมืองที่อยู่บนสายนั้นแน่ๆ แล้วเดินตามทิศการไหลลงไป
# จนถึงจุดที่พื้นที่รับน้ำกระโดด > JUMP เท่า = บรรจบสายที่ใหญ่กว่า (วัง→ปิง, ยม→น่าน, ปิง+น่าน→เจ้าพระยา)
# (ครั้งแรกใช้ "ช่วงพื้นที่รับน้ำ" ใกล้จุดบรรจบ แต่ยมไปจับน่านช่วงพิจิตรแทน จึงเปลี่ยนมาวิธีนี้)
SEEDS = [("wang", (18.29, 99.49)), ("yom", (17.01, 99.82)), ("nan", (17.62, 100.10)),
         ("ping", (18.79, 98.98)), ("pasak", (16.42, 101.16))]
JUMP = 1.45


def km(a, b):
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0]))) * 111.2


def seed_seg(pt, r=6):
    best = None
    for k in bset:
        v = S[k]
        if min(km(pt, q) for q in v["g"]) <= r and (best is None or v["up"] > S[best]["up"]):
            best = k
    return best


def walk_to_outlet(k):
    while S[k]["dn"] in S and S[S[k]["dn"]]["up"] < S[k]["up"] * JUMP:
        k = S[k]["dn"]
    return k


outlet = {name: walk_to_outlet(seed_seg(pt)) for name, pt in SEEDS}
print({n: (k, S[k]["up"], S[k]["g"][-1]) for n, k in outlet.items()})
out_ids = {k: n for n, k in outlet.items() if k}

group = {}
for k in basin:
    cur, g = k, "cpy"
    seen = 0
    while cur in S and seen < 2000:
        if cur in out_ids:
            g = out_ids[cur]
            # วังอยู่ต้นน้ำของปิง: ถ้าเจอวังก่อนก็จบที่วัง / ยมก่อนน่าน
            break
        cur = S[cur]["dn"]
        seen += 1
    group[k] = g

res = {g: [] for g in ("ping", "wang", "yom", "nan", "pasak", "cpy")}
for k in basin:
    res[group[k]].append({"up": S[k]["up"], "g": [[round(a, 3), round(b, 3)] for a, b in S[k]["g"][::2] + [S[k]["g"][-1]]]})
json.dump(res, open(OUT, "w"), separators=(",", ":"))
print("OK", OUT, {g: len(v) for g, v in res.items()}, f"{os.path.getsize(OUT) / 1e3:.0f} KB")
