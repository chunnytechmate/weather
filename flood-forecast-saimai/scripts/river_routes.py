#!/usr/bin/env python3
"""เส้นทางน้ำจริงจากเขื่อนไปปลายน้ำ ตามเส้นแม่น้ำของ OpenStreetMap -> data/geo/routes.json

ทำไมต้องทำ: น้ำไม่ได้ลงใต้เป็นเส้นตรง ลุ่มอีสานไหลตะวันออกลงโขง น้ำอูน/ห้วยหลวงไหลขึ้นเหนือ
ป่าสักถูกผันเข้าคลองระพีพัฒน์ไปตะวันออกเฉียงใต้ ท่าจีนแยกไปตะวันตก

วิธี: ดึง waterway=river ทั้งประเทศ (แบ่งช่อง cache ไว้ใน data/geo/osm/) สร้างกราฟจากโหนดของเส้น
แล้วหา shortest path จากเขื่อนผ่าน waypoint (จุดบรรจบ/ปากแม่น้ำ) ตามลำดับใน ROUTES
เส้นที่ชื่อตรงกับแม่น้ำของช่วงนั้นมีน้ำหนักระยะ x1 เส้นอื่น x4 เพื่อให้ path เกาะแม่น้ำสายที่ถูก
แต่ยังข้ามลำน้ำสาขาเล็กที่ไม่มีชื่อได้ ทิศทาง = ลำดับจากเขื่อนไปปลายทาง (ตามการไหลจริง)

รันใหม่เมื่อแก้ ROUTES เท่านั้น เส้นแม่น้ำไม่ต้องอัปเดตรายชั่วโมง"""
import json, os, math, heapq, time, urllib.request, urllib.parse, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OSM = os.path.join(BASE, "data", "geo", "osm")
OUT = os.path.join(BASE, "data", "geo", "routes.json")
HOSTS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
UA = {"User-Agent": "saimai-flood-dashboard/1.0 (chunnytechmate)"}

# ช่องที่ยังไม่มี cache จะดึงเฉพาะ river (ช่องแรกๆ ดึง canal มาด้วย ใช้ได้เหมือนกัน)
TILES = [(5.5, 97.3, 11, 103), (11, 97.3, 14.5, 103), (11, 103, 14.5, 105.7)]
TILES += [(la, lo, la + 1.5, lo + 2.1) for la in (14.5, 16, 17.5, 19) for lo in (97.3, 99.4, 101.5, 103.6)]
# คลองที่เส้นทางป่าสัก → สายไหม ต้องใช้ (ระบบคลองไม่ได้เป็น waterway=river)
CANALS = ["คลองระพีพัฒน์", "คลองรังสิตประยูรศักดิ์", "คลองสอง"]
EXTRA_NAMES = ["น้ำแม่กวง", "แม่น้ำกวง", "ทับเสลา", "แม่น้ำสะแกกรัง", "คลองกระเสียว", "แม่น้ำท่าจีน", "น้ำพรม",
               "ลำน้ำเชิญ", "คลองนางรอง", "๕ลองนางรอง", "ห้วยหลวง", "ลำน้ำพุง", "ห้วยน้ำพุง", "แม่น้ำพุมดวง", "แม่น้ำตาปี"]

# ---- จุดอ้างอิง (lat, lon) ประมาณ แล้ว snap เข้าหาโหนดแม่น้ำที่ใกล้สุด ----
P = {
    "NSW": (15.700, 100.137),        # ปากน้ำโพ ปิง+น่าน = เจ้าพระยา
    "CPY_END": (13.545, 100.585),    # ปากแม่น้ำเจ้าพระยา
    "AYU": (14.352, 100.578),        # ป่าสักรวมเจ้าพระยาที่อยุธยา
    "RAMA6": (14.545, 100.730),      # เขื่อนพระรามหก ท่าเรือ (หัวคลองระพีพัฒน์)
    "RANGSIT_K2": (14.030, 100.660), # คลองรังสิตตัดคลองสอง
    "HOME": (13.918, 100.651),
    "BANTAK": (17.045, 99.080),      # วังรวมปิง
    "CHUMSAENG": (15.895, 100.300),  # ยมรวมน่าน
    "PHROMPHIRAM": (17.030, 100.200),  # แควน้อยรวมน่าน
    "UTHAI": (15.380, 100.080),      # สะแกกรังรวมเจ้าพระยา
    "BHUMIBOL": (17.243, 98.972),
    "LAMPHUN": (18.500, 99.000),
    "THACHIN_END": (13.500, 100.280),
    "SAMCHUK": (14.755, 100.095),    # ลำกระเสียวรวมแม่น้ำท่าจีน (สุพรรณบุรี) แถวสามชุก
    "KAN": (14.020, 99.530),         # แควใหญ่+แควน้อย = แม่กลอง
    "MK_END": (13.365, 100.000),
    "PHET_END": (13.250, 100.090),
    "PRAN_END": (12.410, 99.990),
    "BPK_START": (14.020, 101.250),  # นครนายก+ปราจีน = บางปะกง
    "BPK_END": (13.480, 100.960),
    "PRASAE_END": (12.700, 101.700),
    "RAYONG_END": (12.665, 101.280),
    "PHONG_CHI": (16.260, 103.060),
    "CHI_MUN": (15.310, 104.720),
    "MUN_END": (15.320, 105.500),
    "PHIMAI": (15.220, 102.495),
    "KORAT": (14.975, 102.100),
    "PHIBUN": (15.245, 105.230),
    "NANGRONG": (14.630, 102.790),
    "LAMPAO_CHI": (16.050, 103.650),
    "UBOLRATANA": (16.775, 102.618),
    "PHONPHISAI": (18.020, 103.080),
    "OON_SK": (17.660, 103.990),
    "SK_END": (17.620, 104.550),
    "NONGHAN": (17.170, 104.150),
    "KAM_END": (16.950, 104.740),
    "PHUNPHIN": (9.100, 99.210),
    "TAPI_END": (9.170, 99.340),
    "PATTANI_END": (6.880, 101.250),
    "CHI_UPPER": (16.200, 102.030),
}
CPY = ["แม่น้ำเจ้าพระยา"]
# แต่ละ route = ลำดับ leg (ปลายทาง, ชื่อลำน้ำที่ควรเกาะ); จุดเริ่มคือพิกัดเขื่อน
# route ที่สองขึ้นไป (เช่น ป่าสักแยกเข้าคลอง) ใส่เป็น list ของ route
ROUTES = {
    "ภูมิพล": [[("NSW", ["แม่น้ำปิง"]), ("CPY_END", CPY)]],
    "สิริกิติ์": [[("NSW", ["แม่น้ำน่าน"]), ("CPY_END", CPY)]],
    "แควน้อยบำรุงแดน": [[("PHROMPHIRAM", ["แม่น้ำแควน้อย"]), ("NSW", ["แม่น้ำน่าน"]), ("CPY_END", CPY)]],
    "กิ่วคอหมา": [[("BANTAK", ["แม่น้ำวัง"]), ("NSW", ["แม่น้ำปิง"])]],
    "กิ่วลม": [[("BANTAK", ["แม่น้ำวัง"]), ("NSW", ["แม่น้ำปิง"])]],
    "แม่มอก": [[("CHUMSAENG", ["แม่น้ำยม"])]],
    "แม่งัดสมบูรณ์ชล": [[("BHUMIBOL", ["แม่น้ำปิง"])]],
    "แม่กวงอุดมธารา": [[("LAMPHUN", ["แม่น้ำกวง", "น้ำแม่กวง", "แม่น้ำปิง"]), ("BHUMIBOL", ["แม่น้ำปิง"])]],
    "ทับเสลา": [[("UTHAI", ["ทับเสลา", "แม่น้ำสะแกกรัง"]), ("CPY_END", CPY)]],
    "ป่าสักชลสิทธิ์": [[("AYU", ["แม่น้ำป่าสัก"]), ("CPY_END", CPY)],
                       [("RAMA6", ["แม่น้ำป่าสัก"]), ("RANGSIT_K2", ["คลองระพีพัฒน์", "คลองรังสิตประยูรศักดิ์"]),
                        ("HOME", ["คลองสอง"])]],
    "กระเสียว": [[("SAMCHUK", ["คลองกระเสียว"]), ("THACHIN_END", ["แม่น้ำท่าจีน"])]],
    "ศรีนครินทร์": [[("KAN", ["แม่น้ำแควใหญ่"]), ("MK_END", ["แม่น้ำแม่กลอง"])]],
    "ท่าทุ่งนา": [[("KAN", ["แม่น้ำแควใหญ่"]), ("MK_END", ["แม่น้ำแม่กลอง"])]],
    "วชิราลงกรณ": [[("KAN", ["แม่น้ำแควน้อย"]), ("MK_END", ["แม่น้ำแม่กลอง"])]],
    "แก่งกระจาน": [[("PHET_END", ["แม่น้ำเพชรบุรี"])]],
    "ปราณบุรี": [[("PRAN_END", ["แม่น้ำปราณบุรี"])]],
    "ขุนด่านปราการชล": [[("BPK_START", ["แม่น้ำนครนายก"]), ("BPK_END", ["แม่น้ำบางปะกง"])]],
    "นฤบดินทรจินดา": [[("BPK_START", ["แม่น้ำปราจีนบุรี"]), ("BPK_END", ["แม่น้ำบางปะกง"])]],
    "คลองสียัด": [[("BPK_END", ["คลองท่าลาด", "แม่น้ำบางปะกง"])]],
    "ประแสร์": [[("PRASAE_END", ["แม่น้ำประแสร์"])]],
    "หนองปลาไหล": [[("RAYONG_END", ["คลองใหญ่", "แม่น้ำระยอง"])]],
    "อุบลรัตน์": [[("PHONG_CHI", ["ลำน้ำพอง"]), ("CHI_MUN", ["แม่น้ำชี"]), ("MUN_END", ["แม่น้ำมูล"])]],
    "จุฬาภรณ์": [[("UBOLRATANA", ["น้ำพรม", "ลำน้ำเชิญ"])]],
    "ห้วยกุ่ม": [[("UBOLRATANA", ["น้ำพรม", "ลำน้ำเชิญ"])]],
    "ลำปาว": [[("LAMPAO_CHI", ["ลำน้ำปาว"]), ("CHI_MUN", ["แม่น้ำชี"])]],
    "ลำตะคอง": [[("KORAT", ["ลำตะคอง"]), ("PHIMAI", ["ลำตะคอง", "แม่น้ำมูล"])]],
    "ลำพระเพลิง": [[("PHIMAI", ["ลำพระเพลิง", "แม่น้ำมูล"])]],
    "มูลบน": [[("PHIMAI", ["แม่น้ำมูล"])]],
    "ลำแชะ": [[("PHIMAI", ["แม่น้ำมูล"])]],
    "ลำนางรอง": [[("NANGRONG", ["คลองนางรอง", "๕ลองนางรอง"])]],
    "สิรินธร": [[("PHIBUN", ["ลำโดมน้อย"]), ("MUN_END", ["แม่น้ำมูล"])]],
    "ปากมูล": [[("MUN_END", ["แม่น้ำมูล"])]],
    "ห้วยหลวง": [[("PHONPHISAI", ["ห้วยหลวง"])]],
    "น้ำอูน": [[("SK_END", ["ลำน้ำอูน", "แม่น้ำสงคราม"])]],
    "น้ำพุง": [[("NONGHAN", ["ลำน้ำพุง", "ห้วยน้ำพุง"])]],
    "รัชชประภา": [[("PHUNPHIN", ["แม่น้ำพุมดวง"]), ("TAPI_END", ["แม่น้ำตาปี"])]],
    "บางลาง": [[("PATTANI_END", ["แม่น้ำปัตตานี"])]],
}
ROUTE_START = {}  # (เขื่อน, ลำดับ route) -> จุดเริ่มที่ไม่ใช่ตัวเขื่อน


def overpass(q):
    for a in range(8):
        h = HOSTS[a % len(HOSTS)]
        try:
            req = urllib.request.Request(h, data=urllib.parse.urlencode({"data": q}).encode(), headers=UA)
            raw = urllib.request.urlopen(req, timeout=200).read()
            return json.loads(raw)
        except Exception as e:
            print("  retry", a, h.split("/")[2], e, flush=True)
            time.sleep(15)
    raise SystemExit("Overpass ไม่ตอบ ลองใหม่ภายหลัง")


def load_ways():
    os.makedirs(OSM, exist_ok=True)
    ways = []
    for s, w, n, e in TILES:
        f = os.path.join(OSM, f"t_{s}_{w}_{n}_{e}.json")
        if not os.path.exists(f):
            print("download tile", (s, w, n, e), flush=True)
            d = overpass(f'[out:json][timeout:180];way["waterway"="river"]({s},{w},{n},{e});out geom;')
            json.dump(d, open(f, "w"))
        ways += json.load(open(f))["elements"]
    f = os.path.join(OSM, "canals.json")
    if not os.path.exists(f):
        rx = "|".join(CANALS)
        d = overpass(f'[out:json][timeout:120];way["waterway"]["name"~"^({rx})$"](13.5,100.3,14.8,101.2);out geom;')
        json.dump(d, open(f, "w"))
    ways += json.load(open(f))["elements"]
    # เส้นที่เป็นสมาชิกของ river relation: หลายช่วง (เช่น ปิงใต้เขื่อนภูมิพล) ไม่ได้ติด waterway ที่ตัวเส้น
    # ติดไว้ที่ relation ทั้งสายแทน จึงไม่ติดมากับ query ข้างบน ดึงแยกแล้วใส่ชื่อจาก relation ให้
    f = os.path.join(OSM, "relations.json")
    if not os.path.exists(f):
        d = overpass('[out:json][timeout:250];relation["waterway"="river"](5.5,97.3,20.6,105.7)->.r;'
                     '.r out body;way(r.r);out geom;')
        json.dump(d, open(f, "w"))
    els = json.load(open(f))["elements"]
    relname = {}
    for r in els:
        if r["type"] == "relation":
            for m in r.get("members", []):
                if m["type"] == "way":
                    relname.setdefault(m["ref"], (r.get("tags") or {}).get("name", ""))
    for w in els:
        if w["type"] == "way":
            tags = dict(w.get("tags") or {})
            if not tags.get("name") and relname.get(w["id"]):
                tags["name"] = relname[w["id"]]
            ways.append({**w, "tags": tags})
    # ลำน้ำสาขาของเขื่อนเล็กมักเป็น waterway=stream ดึงเฉพาะตามชื่อที่ต้องใช้
    f = os.path.join(OSM, "named_extra.json")
    if not os.path.exists(f):
        rx = "|".join(EXTRA_NAMES)
        d = overpass(f'[out:json][timeout:200];way["waterway"~"^(river|stream|canal)$"]["name"~"^({rx})$"]'
                     '(5.5,97.3,20.6,105.7);out geom;')
        json.dump(d, open(f, "w"))
    ways += [w for w in json.load(open(f))["elements"] if (w.get("tags") or {}).get("waterway") != "dam"]
    return ways


def km(a, b):
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0]))) * 111.2


# ---- กราฟ: โหนดคือพิกัดปัด 5 ตำแหน่ง (เส้นที่ต่อกันใน OSM ใช้โหนดร่วม) ----
ways = load_ways()
seen = set()
adj = {}          # node -> [(node, km, name)]
wayof = {}        # node -> {way id} ใช้กันไม่ให้เชื่อมรอยขาดกลับเข้าเส้นเดิม
names = {}        # node -> {ชื่อลำน้ำ}
coords = {}
for wy in ways:
    if wy["id"] in seen or "geometry" not in wy:
        continue
    seen.add(wy["id"])
    name = (wy.get("tags") or {}).get("name", "")
    pts = [(round(g["lat"], 5), round(g["lon"], 5)) for g in wy["geometry"] if g]
    for p in pts:
        wayof.setdefault(p, set()).add(wy["id"])
        names.setdefault(p, set()).add(name)
    for a, b in zip(pts, pts[1:]):
        d = km(a, b)
        adj.setdefault(a, []).append((b, d, name))
        adj.setdefault(b, []).append((a, d, name))
# grid index สำหรับหาโหนดใกล้สุด
GRID = {}
for p in adj:
    GRID.setdefault((int(p[0] * 20), int(p[1] * 20)), []).append(p)

# ---- เชื่อมรอยขาด: เส้นแม่น้ำใน OSM ขาดตรงอ่างเก็บน้ำ ฝาย ตัวเมือง หรือจุดที่ mapper ไม่ได้ต่อโหนด
# ปลายเส้นที่ห้อย (degree 1) ต่อเข้าโหนดของเส้นอื่นที่ใกล้สุดในรัศมี BRIDGE_KM น้ำหนัก x3
BRIDGE_KM = 6.0
ends = [p for p, e in adj.items() if len(e) == 1]
DEAD = set(ends)
bridges = 0
for p in ends:
    mine = wayof[p]
    gy, gx = int(p[0] * 20), int(p[1] * 20)
    best = None
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            for q in GRID.get((gy + dy, gx + dx), []):
                if q == p or wayof[q] & mine:
                    continue
                d = km(p, q)
                if d < BRIDGE_KM and (best is None or d < best[0]):
                    best = (d, q)
    if best:
        adj[p].append((best[1], best[0] * 3, "~"))
        adj[best[1]].append((p, best[0] * 3, "~"))
        bridges += 1
print(f"graph nodes={len(adj)} ways={len(seen)} dead_ends={len(ends)} bridged={bridges}", flush=True)


def nearest(pt, prefer=()):
    """โหนดใกล้สุด ถ้ามีเส้นชื่อที่ต้องการในรัศมี ~8 กม. ให้เลือกเส้นนั้นก่อน"""
    gy, gx = int(pt[0] * 20), int(pt[1] * 20)
    best, bestp = None, None
    for r in range(0, 8):
        cand = [p for dy in range(-r, r + 1) for dx in range(-r, r + 1)
                if max(abs(dy), abs(dx)) == r for p in GRID.get((gy + dy, gx + dx), [])]
        for p in cand:
            d = km(pt, p)
            if best is None or d < best[0]:
                best = (d, p)
            if prefer and any(e[2] in prefer for e in adj[p]) and (bestp is None or d < bestp[0]):
                bestp = (d, p)
        if bestp and r >= 3:
            break
    if bestp and bestp[0] < 8:
        return bestp[1], bestp[0]
    return (best[1], best[0]) if best else (None, None)


GAPS = []


JUMP_KM = 15.0
FALLBACK_KM = 90.0


def jumps(u, prefer):
    """ปลายเส้นที่ห้อย (มักเป็นขอบอ่างเก็บน้ำ/ฝาย) กระโดดไปเส้นชื่อที่ต้องการได้ไม่เกิน JUMP_KM น้ำหนัก x5"""
    if u not in DEAD or not prefer:
        return []
    gy, gx = int(u[0] * 20), int(u[1] * 20)
    out = []
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            for q in GRID.get((gy + dy, gx + dx), []):
                if names[q] & prefer and not (wayof[q] & wayof[u]):
                    d = km(u, q)
                    if d <= JUMP_KM:
                        out.append((q, d * 5, "jump"))
    return out


def path(a, b, prefer):
    """Dijkstra: เส้นชื่อที่ต้องการ x1, เส้นอื่น x4, กระโดดข้ามรอยขาด x5"""
    dist, prev = {a: 0.0}, {}
    pq = [(0.0, a)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w, nm in adj[u] + jumps(u, prefer):
            nd = d + (w if nm == "jump" else w * (1 if nm in prefer else 4))
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    if b not in dist:
        # เส้นแม่น้ำ OSM ขาดยาว: เดินตามแม่น้ำจริงไปถึงจุดที่ใกล้เป้าที่สุด แล้วลากตรงไปเป้า
        # (เส้นตรงช่วงนี้วาดเป็นเส้นประจาง = ประมาณ) ถ้ายังห่างเกิน FALLBACK_KM ถือว่าหาไม่ได้
        c = min(dist, key=lambda n: km(n, b))
        GAPS.append((c, round(km(c, b), 1)))
        if km(c, b) > FALLBACK_KM:
            return None
        out, u = [c], c
        while u != a:
            u = prev[u]
            out.append(u)
        return out[::-1] + [b]
    out, u = [b], b
    while u != a:
        u = prev[u]
        out.append(u)
    return out[::-1]


def simplify(pts, tol=0.002):
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


dams = {d["name"]: (d["lat"], d["lon"]) for d in
        json.load(open(os.path.join(BASE, "data", "dams_verified.json")))["dams"] if d["lat"] is not None}
out, problems = {}, []
for name, routes in ROUTES.items():
    if name not in dams:
        problems.append(f"{name}: ไม่มีพิกัดเขื่อน")
        continue
    out[name] = []
    for ri, legs in enumerate(routes):
        cur_pt = ROUTE_START.get((name, ri), dams[name])
        cur, off = nearest(cur_pt, legs[0][1])
        if off is not None and off > 12:
            problems.append(f"{name}#{ri}: เขื่อนห่างแม่น้ำใกล้สุด {off:.1f} กม.")
        line, gaps = [], []
        for tgt, prefer in legs:
            b, boff = nearest(P[tgt], prefer)
            p = path(cur, b, set(prefer)) if cur and b else None
            if not p:
                g = GAPS[-1] if GAPS else ("?", "?")
                problems.append(f"{name}#{ri}: หาเส้นทางไป {tgt} ไม่ได้ (ไปได้ไกลสุดถึง {g[0]} ห่างเป้า {g[1]} กม.)")
                break
            if p[-2:] and len(p) > 1 and not any(v == p[-1] for v, _, _ in adj[p[-2]]) and km(p[-2], p[-1]) > 1:
                problems.append(f"{name}#{ri}: ช่วงไป {tgt} ใช้เส้นประมาณ {km(p[-2], p[-1]):.0f} กม.")
            if boff > 5:
                problems.append(f"{name}#{ri}: {tgt} ห่างแม่น้ำ {boff:.1f} กม.")
            line += p if not line else p[1:]
            cur = b
            # ช่วงที่ไม่ใช่ขอบในกราฟ = กระโดดข้ามรอยขาด (> 1 กม.) วาดเป็นเส้นประจาง
            for x, y in zip(p, p[1:]):
                if km(x, y) > 1 and not any(v == y for v, _, _ in adj[x]):
                    gaps.append([list(x), list(y)])
        # จุดเริ่มอาจไปจับเส้นแม่น้ำในอ่างเหนือเขื่อน: ตัดส่วนต้นให้เริ่มที่โหนดใกล้ตัวเขื่อนที่สุด
        if len(line) > 3:
            head = line[:max(2, len(line) * 2 // 5)]
            i0 = min(range(len(head)), key=lambda i: km(head[i], cur_pt))
            line = line[i0:]
            gaps = [g for g in gaps if tuple(g[0]) in set(line)]
        if len(line) > 1:
            # ต่อเส้นประจากตัวเขื่อนถึงจุดแรกบนแม่น้ำ ให้เห็นว่าเริ่มจากเขื่อนจริง
            out[name].append({"from_dam": list(cur_pt), "line": [list(x) for x in simplify(line)], "gaps": gaps,
                              "km": round(sum(km(a, b) for a, b in zip(line, line[1:])))})

json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print(f"OK {OUT} dams={len(out)} routes={sum(len(v) for v in out.values())} "
      f"size={os.path.getsize(OUT)/1e3:.0f} KB")
for name, rs in out.items():
    print(" ", name, [r["km"] for r in rs])
for p in problems:
    print("  WARN", p)
