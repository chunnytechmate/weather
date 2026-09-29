#!/usr/bin/env python3
"""โมเดล forecast ระดับน้ำรายวัน 90 วัน (lag-route + wave translation + exponential recession)
   สร้าง fc_days.json ให้ build_dashboard_v2 ฝังลง timeline

   3 tier ของ input (ความเชื่อมั่นต่างกัน แถบ lo/hi จึงกว้างขึ้นตาม tier):
   - tier 1 (วัน 1-16): ฝนจาก NWP Open-Meteo (forecast_days=16)
   - tier 2 (วัน 17-35): ฝนจาก Seasonal API (ECMWF SEAS5) เรียบด้วย rolling mean 5 วัน
   - tier 3 (วัน 36-90): SEAS5 เสื่อมสภาพแล้ว อ่านเป็นแนวโน้มสถิติฤดูกาลเท่านั้น

   ตัวแปรทั้งหมด: h0/momentum จากค่าอ่าน 18 ชม. + wave บางปะอิน + ฝนเหนือ lag 3 + ฝนท้องถิ่น
   + น้ำไหลเข้าเขื่อนภูมิพล/สิริกิติ์ lag 3-8 วัน (ใหม่, ยังไม่ calibrate) + ตัวคูณน้ำหนุนจากเฟสดวงจันทร์"""
import json, glob, os, datetime, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HORIZON = 90          # จำนวนวัน forecast (วันถัดไป 1..90)
NWP_DAYS = 16         # วันที่ใช้ NWP ได้ (Open-Meteo ให้สูงสุด 16)
SEASONAL_TRUST = 35   # หลังจากวันนี้ SEAS5 เสื่อมลงเหลือระดับ "สถิติฤดูกาล" (tier 3)
SEASONAL_SMOOTH = 5   # rolling-mean วัน สำหรับฝน seasonal

# climatology สำรอง (มม./วัน) กรณี Seasonal API ล่ม — ค่าประมาณปกติต.ค.-ธ.ค. ของ กทม./ภาคเหนือตอนล่าง
CLIMO = {"soi": {"10": 6.0, "11": 2.0, "12": 0.5}, "north": {"10": 4.5, "11": 2.5, "12": 1.0}}

def load_snaps():
    out = []
    for f in sorted(glob.glob(os.path.join(BASE, "data", "snapshots", "snapshot-*.json"))):
        try:
            out.append(json.load(open(f)))
        except Exception:
            pass
    return out

def series_of(snaps, key):
    pts = []
    for sn in snaps:
        for st in sn["stations"]:
            if key in st["name"] or key in st.get("key", ""):
                pts.append((sn["fetched_at"], st["msl"]))
                break
    return pts

def slope_24h(snaps, key, prev=None):
    pts = series_of(snaps, key)
    if len(pts) >= 2:
        t1, h1 = pts[0]; t2, h2 = pts[-1]
        d1 = datetime.datetime.fromisoformat(t1); d2 = datetime.datetime.fromisoformat(t2)
        hrs = max(1.0, (d2 - d1).total_seconds() / 3600)
        return (h2 - h1) / (hrs / 24.0)
    if prev is not None:
        return prev
    return 0.0

def daily_means(snaps, key):
    """ค่าเฉลี่ยรายวันของสถานีจากประวัติ snapshot — กลบวัฏจักรน้ำหนุนรายวัน (~±20 ซม.)
       ให้ h0/v0 เป็นสัญญาณระดับน้ำจริง ไม่ใช่ phase น้ำขึ้น-ลงของ snapshot สุดท้าย"""
    per_day = {}
    for sn in snaps:
        for st in sn["stations"]:
            if key in st["name"] or key in st.get("key", ""):
                per_day.setdefault(sn["fetched_at"][:10], []).append(st["msl"])
                break
    return [(d, sum(v) / len(v)) for d, v in sorted(per_day.items()) if v]

def canal_daily_means(snaps, frag):
    per_day = {}
    for sn in snaps:
        for c in sn.get("canals", []):
            if frag in c.get("name", ""):
                try:
                    per_day.setdefault(sn["fetched_at"][:10], []).append(float(c["value"]))
                except (TypeError, ValueError):
                    pass
                break
    return [(d, sum(v) / len(v)) for d, v in sorted(per_day.items()) if v]

def parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(str(s)[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(str(s)[:19])
    except ValueError:
        return None

def dt_series(snaps, key, canal=False):
    """[(dt, val)] ของสถานี — dedupe ตาม timestamp ของตัวค่าอ่านเอง (ไม่ใช่เวลา fetch)
       เพื่อตัดค่า stale ที่สถานียังไม่อัปเดตออกจากการเฉลี่ย"""
    out = {}
    for sn in snaps:
        if canal:
            for c in sn.get("canals", []):
                if key in c.get("name", ""):
                    d = parse_dt(c.get("dt"))
                    try:
                        v = float(c["value"])
                    except (TypeError, ValueError):
                        v = None
                    if d and v is not None and (d not in out or out[d] is None):
                        out[d] = v
                    break
        else:
            for st in sn["stations"]:
                if key in st["name"] or key in st.get("key", ""):
                    d = parse_dt(st.get("dt"))
                    if d and d not in out:
                        out[d] = st["msl"]
                    break
    return sorted(out.items())

def level_and_momentum(snaps, key, latest_val, prev_val=None, canal=False):
    """คืน (h0, v0): h0 = เฉลี่ยค่าอ่าน 18 ชม.ล่าสุด (ครอบ 1 รอบน้ำหนุน, ตัด stale ด้วย dt),
       v0 = อัตราเปลี่ยน (ม./วัน) เทียบ window 18 ชม.ก่อนหน้า — fallback ค่าล่าสุด/slope 24 ชม."""
    t_end = datetime.datetime.fromisoformat(snaps[-1]["fetched_at"])
    ser = dt_series(snaps, key, canal=canal)
    if not ser:
        return latest_val, (0.0 if canal else slope_24h(snaps, key, prev_val))
    rec = [v for d, v in ser if d >= t_end - datetime.timedelta(hours=18)]
    prev = [v for d, v in ser
            if t_end - datetime.timedelta(hours=36) <= d < t_end - datetime.timedelta(hours=18)]
    h0 = sum(rec) / len(rec) if rec else ser[-1][1]
    v0 = ((sum(rec) / len(rec) - sum(prev) / len(prev)) / 0.75) if (rec and prev) \
        else (0.0 if canal else slope_24h(snaps, key, prev_val))
    return h0, v0

FST = [
    # rain_coef ปรับ 28/9/69: ค่าเดิม (คลอง 0.08–0.10 ม./มม.) สูงผิดสัดส่วน — ฝน 10 มม. ยกคลอง +1 ม.
    # เป็นไปไม่ได้ และค่าเดิมรอดมาได้เพราะโดน ceiling กลบ → สเกลใหม่ ~0.002–0.003 (ฝน 20 มม. ≈ +4–6 ซม.)
    # แม่น้ำใช้ 0.0005–0.001 · รอ fit จากประวัติ snapshot เมื่อสะสมครบหลายวันตามแผนเดิม
    {"key": "บางปะอิน", "name": "บางปะอิน (เจ้าพระยา)", "ref": "bank", "K": 0.10, "lag_up": 0, "rain_coef": 0.001, "drop_cap": 0.9, "grp": "river"},
    {"key": "สามเสน", "name": "กรมชลฯ สามเสน (เจ้าพระยา)", "ref": "bank", "K": 0.075, "lag_up": 1, "rain_coef": 0.0005, "drop_cap": 0.8, "grp": "river"},
    {"key": "สะพานกรุงเทพ", "name": "สะพานกรุงเทพ (เจ้าพระยา)", "ref": "bank", "K": 0.07, "lag_up": 1, "rain_coef": 0.0005, "drop_cap": 0.7, "grp": "river"},
    {"key": "นวลฉวี", "name": "สะพานนวลฉวี (ปากคลองลาดพร้าว)", "ref": "bank", "K": 0.07, "lag_up": 1, "rain_coef": 0.0005, "drop_cap": 0.7, "grp": "river"},
    {"key": "ปากคลอง2สายใต้", "name": "คลองหกวา ปากคลอง 2 (RID)", "ref": "crit", "K": 0.16, "lag_up": 1, "rain_coef": 0.003, "drop_cap": 0.9, "grp": "khlong"},
    {"key": "ท้ายปตร.คลอง2", "name": "คลองหกวา ท้าย ปตร.คลอง 2 (RID)", "ref": "crit", "K": 0.16, "lag_up": 1, "rain_coef": 0.003, "drop_cap": 0.9, "grp": "khlong"},
    {"key": "คลองหกวา ลำลูกกา คลอง8", "name": "คลองหกวา ลำลูกกา คลอง 8", "ref": "crit", "K": 0.14, "lag_up": 2, "rain_coef": 0.0025, "drop_cap": 0.8, "grp": "khlong"},
    {"key": "คลองเปรมประชากร หลักหก", "name": "คลองเปรมฯ หลักหก", "ref": "crit", "K": 0.15, "lag_up": 1, "rain_coef": 0.003, "drop_cap": 0.8, "grp": "khlong"},
    {"key": "คลองระพีพัฒน์แยกตก", "name": "คลองระพีพัฒน์แยกตก", "ref": "bank", "K": 0.12, "lag_up": 1, "rain_coef": 0.002, "drop_cap": 0.8, "grp": "khlong"},
    {"key": "ปตร.คลองสองสายใต้", "name": "ปตร.คลองสองสายใต้ (เซ็นเซอร์ กทม.)", "ref": "bma", "K": 0.14, "lag_up": 1, "rain_coef": 0.003, "drop_cap": 0.7, "grp": "canal"},
]

CRIT_FALLBACK = {"ปากคลอง2สายใต้": 2.10, "ท้ายปตร.คลอง2": 1.95, "คลองเปรมประชากร หลักหก": 1.50,
                 "คลองหกวา ลำลูกกา คลอง8": 2.00}

# ---- น้ำหนุน (spring–neap) จากดาราศาสตร์ ----
SYNODIC = 29.530588853
NEW_MOON_EPOCH = 2451550.26  # JD ของ new moon 2000-01-06 18:14 UTC

def moon_phase_frac(d):
    """เฟสดวงจันทร์ 0=ข้างขึ้นใหม่ 0.5=เต็มดวง (คำนวณจาก synodic month เฉลี่ย)"""
    jd = d.toordinal() + 1721424.5 + 0.5
    return ((jd - NEW_MOON_EPOCH) / SYNODIC) % 1.0

def tide_mult(d):
    """ตัวคูณการระบาย: 1.0 = น้ำแล้ง (neap) พื้นฐาน, ต่ำสุด ~0.45 ช่วง spring (ข้างขึ้น/ข้างแรมใหม่ ±2-3 วัน)
       เทียบชดเชยกับค่า hardcode เดิม: 28/9/69=0.45 29/9=0.55 30/9=0.80"""
    ph = moon_phase_frac(d)
    springness = (1.0 + math.cos(4.0 * math.pi * ph)) / 2.0   # พีคที่ new/full moon
    return 1.0 - 0.55 * springness

def rolling_mean(xs, w=SEASONAL_SMOOTH):
    out, n = [], len(xs)
    for i in range(n):
        lo = max(0, i - w // 2); hi = min(n, i + w // 2 + 1)
        out.append(sum(xs[lo:hi]) / (hi - lo))
    return out

def build():
    snaps = load_snaps()
    sn = snaps[-1]
    # ระดับน้ำปกติ (จาก scripts/normal_levels.py — ประวัติ 60 วัน หรือเกณฑ์ทางการ)
    try:
        _nl = json.load(open(os.path.join(BASE, "data", "normal_levels.json")))
        NORM_ST = _nl.get("stations") or {}
        NORM_CAN = _nl.get("canals") or {}
    except Exception:
        NORM_ST, NORM_CAN = {}, {}

    today = datetime.date.fromisoformat(sn["fetched_at"][:10])
    dates = [(today + datetime.timedelta(days=i)).isoformat() for i in range(1, HORIZON + 1)]

    st_by_key = {s["key"]: s for s in sn["stations"]}
    def find(key):
        if key in st_by_key: return st_by_key[key]
        for s in sn["stations"]:
            if key in s["name"]: return s
        return None

    # ---- ฝนเหนือ: รวม 4 จุด เป็นค่าเฉลี่ยรายวัน (tier1 = NWP 16 วัน, tier2 = seasonal smoothed) ----
    north_nwp = {}
    for w in sn.get("wx_north", []):
        for t, p in zip(w.get("time", []), w.get("precip", [])):
            try: north_nwp[t] = north_nwp.get(t, 0.0) + float(p or 0)
            except (TypeError, ValueError): pass
    npts = max(1, len(sn.get("wx_north", [])))
    north_nwp = {d: v / npts for d, v in north_nwp.items()}

    seasonal = sn.get("wx_seasonal") or {}
    north_sea = {}
    sea_n = seasonal.get("north") or []
    for w in sea_n:
        for t, p in zip(w.get("time", []), w.get("precip", [])):
            try: north_sea[t] = north_sea.get(t, 0.0) + float(p or 0)
            except (TypeError, ValueError): pass
    if sea_n:
        north_sea = {d: v / len(sea_n) for d, v in north_sea.items()}
    # เรียบด้วย rolling mean ตามลำดับวันที่
    if north_sea:
        ks = sorted(north_sea)
        sm = rolling_mean([north_sea[k] for k in ks])
        north_sea = dict(zip(ks, sm))

    soi_sea = {}
    if seasonal.get("soi"):
        s = seasonal["soi"]
        ks = s.get("time", []); vs = [float(p or 0) for p in s.get("precip", [])]
        soi_sea = dict(zip(ks, rolling_mean(vs)))

    def north_rain(d):
        v = north_nwp.get(d)
        if v is not None:
            return v, 1
        v = north_sea.get(d)
        if v is not None:
            return v, 2
        return CLIMO["north"].get(d[5:7], 2.0), 2

    def soi_rain(d):
        v = soi_by_day.get(d)
        if v is not None:
            return float(v or 0), 1
        v = soi_sea.get(d)
        if v is not None:
            return v, 2
        return CLIMO["soi"].get(d[5:7], 2.0), 2

    wd = sn.get("wx_daily", {})
    soi_by_day = dict(zip(wd.get("time", []), wd.get("precipitation_sum", [])))

    # ---- น้ำไหลเข้าเขื่อน ภูมิพล+สิริกิติ์ (ล้าน ลบ.ม./วัน): ตัวแปรใหม่ 29/9/69 ----
    # inflow สูงต่อเนื่อง = กดดันให้ต้องระบาย ผลลากถึงบางปะอิน ~3-8 วัน
    # (ใช้ inflow แทนค่าระบาย เพราะ thaiwater ส่ง dam_uses_water เป็นยอดสะสมรายปี ส่วน dam_released มีเฉพาะระบายผ่านทางระบาย)
    # สัมประสิทธิ์อนุรักษ์นิยม + มี cap เพราะยังไม่ได้ calibrate กับเหตุการณ์จริง
    DAM_IN_BASE = 150.0
    dam_in = 0.0
    for d in sn.get("dams", []):
        if any(k in d["name"] for k in ("ภูมิพล", "สิริกิติ์")) and d.get("inflow"):
            try:
                dam_in += float(d["inflow"])
            except (TypeError, ValueError):
                pass

    def dam_push(i):
        if 3 <= i + 1 <= 8:
            return min(0.03, max(0.0, dam_in - DAM_IN_BASE) / 1000.0)
        return 0.0

    # ---- สถานะบางปะอิน (ต้นน้ำเข้าเมือง): momentum + ระดับเหนือตลิ่ง ----
    bpa = find("บางปะอิน")
    bank_bpa = bpa["bank"] if (bpa and bpa.get("bank")) else 2.62
    bpa_h0, v_bpa = level_and_momentum(snaps, "บางปะอิน", bpa["msl"],
                                       (bpa["msl"] - bpa["prev"]) * 0.5 if bpa and bpa.get("prev") else 0.0)
    v_bpa = max(-0.15, min(v_bpa, 0.25))
    bpa_cfg = FST[0]
    bpa_floor = bpa_h0 - bpa_cfg["drop_cap"]
    bpa_ceiling = max(bank_bpa * 1.03, bpa_h0 + 0.02)   # กันเพดานต่ำกว่าระดับปัจจุบัน (แก้ cliff bug)
    bpa_path, h = [], bpa_h0
    for i, d in enumerate(dates):
        north_lag3, _ = north_rain((datetime.date.fromisoformat(d) - datetime.timedelta(days=3)).isoformat())
        soi_v, _ = soi_rain(d)
        tide = tide_mult(datetime.date.fromisoformat(d))
        rise = north_lag3 * 0.0022 + bpa_cfg["rain_coef"] * soi_v + max(0.0, v_bpa) * (math.e ** (-i / 1.2)) + dam_push(i)
        drain = bpa_cfg["K"] * tide * max(0.0, h - bpa_floor)
        if v_bpa < 0:
            drain += min(0.05, -v_bpa * 0.3)
        h = max(bpa_floor, min(bpa_ceiling, h + rise - drain))
        bpa_path.append(h)

    # ---- wave: ส่วนเกินเหนือตลิ่งบางปะอิน ผลักน้ำลงเขตเมือง (lag 1 วัน/ตอน) ----
    def river_up_rise(i):
        wave = 0.30 * max(0.0, bpa_path[max(0, i - 1)] - bank_bpa)
        north_lag3, _ = north_rain((datetime.date.fromisoformat(dates[i]) - datetime.timedelta(days=3)).isoformat())
        return max(0.0, wave + north_lag3 * 0.0022)

    out_st = []
    for idx, st in enumerate(FST):
        if idx == 0:  # บางปะอิน: ใส่ path ที่คำนวณไว้แล้ว
            s = bpa
            h0, ref, warn = bpa_h0, bank_bpa, None
            path, floors, ceils = bpa_path, [bpa_floor] * HORIZON, [bpa_ceiling] * HORIZON
        else:
            s = find(st["key"])
            canal = None
            if st["ref"] == "bma":
                canal = next((c for c in sn.get("canals", []) if st["key"] in c.get("name", "")), None)
            if canal:
                ref = float(canal["crit"]); warn = float(canal["warn"])
                h0, v0 = level_and_momentum(snaps, st["key"], float(canal["value"]), canal=True)
            elif s:
                ref = CRIT_FALLBACK.get(st["key"], s["bank"]) if st["ref"] == "crit" else s["bank"]
                warn = None
                h0, v0 = level_and_momentum(snaps, st["key"], s["msl"],
                                            (s["msl"] - s["prev"]) if s and s.get("prev") else 0.0)
            else:
                continue
            if not ref:
                continue
            v0 = max(-0.2, min(v0, 0.25))
            floor = h0 - st["drop_cap"]
            ceiling = max(ref * (1.12 if st["grp"] != "river" else 1.03), h0 + 0.02)
            path, floors, ceils = [], [], []
            h = h0
            for i, d in enumerate(dates):
                up = river_up_rise(max(0, i - st["lag_up"]))
                soi_v, _ = soi_rain(d)
                tide = tide_mult(datetime.date.fromisoformat(d))
                rise = 0.35 * up + st["rain_coef"] * soi_v + max(0.0, v0) * (math.e ** (-i / 1.2))
                drain = st["K"] * tide * max(0.0, h - floor)
                if v0 < 0:
                    drain += min(0.05, -v0 * 0.3)
                h = max(floor, min(ceiling, h + rise - drain))
                path.append(h); floors.append(floor); ceils.append(ceiling)

        vals = []
        for i, d in enumerate(dates):
            tier = 1 if i < NWP_DAYS else (2 if i < SEASONAL_TRUST else 3)
            band_cap = 1.00 if st["grp"] == "river" else 0.90
            band = min(0.08 + 0.09 * i, band_cap)
            if tier >= 2:
                band += min(0.30, 0.05 * (i - (NWP_DAYS - 1)))
            if tier == 3:
                band += min(0.60, 0.02 * (i - SEASONAL_TRUST + 1))
            h = path[i]
            vals.append({"d": d, "h": round(h, 2),
                         "lo": round(max(floors[i], h - band), 2),
                         "hi": round(min(ceils[i] + 0.05, h + band), 2),
                         "tier": tier,
                         "rain": round(soi_rain(d)[0], 1),
                         "tide": round(tide_mult(datetime.date.fromisoformat(d)), 2)})
        # ระดับปกติของสถานีนี้ (median ประวัติ 60 วัน) + วันแรกที่คาดกลับปกติ
        nv = NORM_ST.get(st["key"])
        if nv is None:   # ชื่อในไฟล์ normal อาจยาวกว่า key ของเรา (เช่น "กรมชลประทานสามเสน")
            for k, v in NORM_ST.items():
                if st["key"] in k or k in st["name"]:
                    nv = v
                    break
        normal = (nv or {}).get("normal")
        normal_src = (nv or {}).get("source")
        if normal is None and st["ref"] == "bma":
            for cn, cv in NORM_CAN.items():
                if st["key"] in cn:
                    normal, normal_src = cv.get("normal"), cv.get("source")
                    break
        back_normal = None
        if normal is not None:
            back_normal = next((v["d"] for v in vals if v["h"] <= normal), None)
        # หมุดหมายที่ actionable กว่า: canal ใช้เกณฑ์เตือนภัย (น้ำไม่ท่วมซอย) แทนค่าปกติทางสถิติ
        ok_thr = warn if (st["ref"] == "bma" and warn) else normal
        back_ok = next((v["d"] for v in vals if ok_thr is not None and v["h"] <= ok_thr), None)

        out_st.append({"name": st["name"], "key": st["key"], "grp": st["grp"], "h0": round(h0, 2),
                       "ref": round(ref, 2) if ref else None, "warn": warn,
                       "normal": normal, "normal_src": normal_src,
                       "back_normal": back_normal, "back_ok": back_ok or back_normal,
                       "series": vals})

    result = {"built_at": sn["fetched_at"], "dates": dates, "nwp_days": NWP_DAYS,
              "seasonal_trust": SEASONAL_TRUST, "horizon": HORIZON,
              "v_bpa": round(v_bpa, 3), "dam_inflow_mcm": round(dam_in, 1),
              "bpa_excess": round(bpa_h0 - bank_bpa, 2),
              "north_by_day": {k: round(v, 1) for k, v in north_nwp.items()},
              "stations": out_st,
              "note": ("โมเดล lag-route 90 วัน: h(t)=h(t-1)+rise−drain · rise = wave จากส่วนเกินเหนือตลิ่งบางปะอิน×0.30 (lag 1 วัน/ตอน) "
                       "+ ฝนเหนือ lag 3 วัน + ฝนท้องถิ่น + momentum สถานี + น้ำไหลเข้าเขื่อนภูมิพล+สิริกิติ์ lag 3-8 วัน (ใหม่ ยังไม่ calibrate) "
                       "· drain = K × ตัวคูณน้ำหนุน (เฟสดวงจันทร์: 1.0 น้ำแล้ง → ~0.45 spring) × ส่วนเกินเหนือระดับล่าง · "
                       "tier 1 วัน 1-16 ฝน NWP Open-Meteo / tier 2 วัน 17-35 SEAS5 / tier 3 วัน 36-90 สถิติฤดูกาล · "
                       "ทั้งหมดเป็นการคาดการเชิงสถิติ พารามิเตอร์ตั้งมืออิงสถิติปี 2554 ยังไม่ได้ fit จากข้อมูลจริง "
                       "· แถบ lo/hi = ความไม่แน่นอนสะสม ±(8+9i) ซม. มีเพดาน 90-100 ซม. + ขยายตาม tier")}
    out = os.path.join(BASE, "data", "fc_days.json")
    json.dump(result, open(out, "w"), ensure_ascii=False)
    print("OK", out, "| stations:", len(out_st), "| dates:", dates[0], "->", dates[-1])
    print(f"  v_bpa={v_bpa:+.3f} บางปะอินเหนือตลิ่ง {bpa_h0 - bank_bpa:+.2f} ม. | tide ตรวจสอบ: "
          f"28/9={tide_mult(datetime.date(2026,9,28)):.2f} 29/9={tide_mult(datetime.date(2026,9,29)):.2f} "
          f"30/9={tide_mult(datetime.date(2026,9,30)):.2f} 11/10={tide_mult(datetime.date(2026,10,11)):.2f} "
          f"26/10={tide_mult(datetime.date(2026,10,26)):.2f}")
    for st in out_st:
        print(f"  {st['name'][:28]:<30}", [v["h"] for v in st["series"]])

if __name__ == "__main__":
    build()
