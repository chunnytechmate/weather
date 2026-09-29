#!/usr/bin/env python3
"""พยากรณ์ผลกระทบสายไหม/ลำลูกกา 14 วัน จากเขื่อน + ธงภัย (สถานีต้นทาง) -> data/impact_forecast.json

เป้าหมาย: ระดับน้ำเฉลี่ยรายวัน (ม.รทก.) ที่
  - สายไหม  : คลองลาดพร้าว ท้ายปตร.คลอง2 (thaiwater id 11, ห่างบ้าน 1.9 กม.)
  - ลำลูกกา : คลองหกวา คลอง8 (id 37)

วิธี: แบบจำลองต่อเป็นโซ่ "linear reservoir" รายวัน (เรียนค่าจากข้อมูล 3 ปี ด้วย OLS, Python ล้วน)
    เขื่อนป่าสัก (ระบาย) → S.28 ท้ายเขื่อน → คลองระพีพัฒน์ → ลำลูกกา (คลองหกวา) → สายไหม
    (S.26 ท้ายเขื่อนพระรามหกถูกคุมด้วยบานประตู fit แล้วไม่มีความหมายทางกายภาพ จึงข้ามไปใช้ S.28 ตรง)
  แยกค่าพารามิเตอร์ 2 ช่วง: ปกติ / น้ำสูง (เกินปกติ > 0.5 ม.) เพราะตอนน้ำสูงสถานีสูบทำงานเต็มกำลัง
  น้ำจึงลดช้าลง และดินอิ่มน้ำทำให้ฝนมีผลมากขึ้น (เช่น สายไหมตอนน้ำสูง ฝน 0.96 ซม./มม. vs ปกติ 0.4)
  แต่ละข้อต่อ: a(t+1) − a(t) = −k·a(t) + β·ต้นทาง(t−lag) + r1·ฝน(t+1) + r0·ฝน(t) + c
    a = ระดับเทียบค่ากลางปกติ · k = อัตราลดกลับสู่ปกติ/วัน · lag เลือกจากค่าที่ fit ดีที่สุด
  เหตุผลที่ไม่ใช้ regression แบบดูภาพรวม: เหตุการณ์ตอนนี้รุนแรงเกินข้อมูลฝึกเกือบทุกตัว (ฝน 7 วัน 267 มม.
  vs สูงสุดเดิม 141, ระดับคลองสูงสุดในรอบ 3 ปี) โมเดลเชิงเส้นแบบภาพรวม extrapolate แกว่ง ±50 ซม.
  ส่วน linear reservoir ลดลงเป็นสัดส่วนกับระดับเสมอ จึงทนค่าสุดโต่งกว่า
  ทดสอบ: จำลองไปข้างหน้า 14 วันจริง (ไม่ใช่ 1 วัน) แบบกันทีละปีน้ำ เทียบ persistence
    (ก) ใช้ฝนจริง = ขอบบนของความแม่นถ้าพยากรณ์ฝนแม่น (ข) ไม่รู้ฝนอนาคต (ฝน = 0)
  ข้อมูลพยากรณ์วันนี้: ฝน Open-Meteo 16 วัน · ระบายป่าสักตามสถานการณ์ (ดู PASAK_SCENARIOS)
ข้อจำกัด: ไม่รู้การเปิด-ปิดประตูน้ำ/สูบน้ำของ กทม. และการผันน้ำของกรมชลฯ · ระดับวันนี้สูงเกินข้อมูลฝึก"""
import json, os, sys, math, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
DIR = os.path.join(BASE, "data", "impact")
ST = json.load(open(os.path.join(DIR, "stations.json")))
DM = json.load(open(os.path.join(DIR, "dams.json")))
RN = json.load(open(os.path.join(DIR, "rain.json")))
HOR = 14
FLAGS = json.load(open(os.path.join(BASE, "data", "river_flags.json")))["flags"]
# ระดับที่ "ท่วมจริงแล้ว" จากประกาศ: ปภ. 29 ก.ย. 2569 เตือน Cell Broadcast เขตสายไหม/คลองสามวา/หนองจอก
# "น้ำคลองหกวาสายล่างล้นคันกั้นน้ำ" (กรุงเทพธุรกิจ 1254210) และลำลูกกาท่วม 40-70 ซม. ตั้งแต่ 25-27 ก.ย. (เดลินิวส์ 6227194)
# ใช้ระดับรายวันต่ำสุดของสถานีช่วงวันที่มีรายงานท่วม เป็น "เกณฑ์ท่วมที่เห็นจริง" (ต่ำกว่าตลิ่งของสถานีมาก
# เพราะคันกั้นน้ำจุดอ่อนริมคลองล้นก่อนถึงตลิ่ง ณ จุดวัด)
FLOOD_OBS = {"11": ("2026-09-26", "2026-09-29", "ปภ. เตือนเขตสายไหม: คลองหกวาสายล่างล้นคันกั้นน้ำ (29 ก.ย.)"),
             "37": ("2026-09-25", "2026-09-27", "ลำลูกกาท่วม 40-70 ซม. หมู่บ้านพฤกษาวิลล์/ซอยลำลูกกา 13 (25-27 ก.ย.)")}
TARGETS = {"11": "สายไหม", "37": "ลำลูกกา"}
CPY_DAMS = ["ภูมิพล", "สิริกิติ์", "แควน้อยบำรุงแดน"]


def D(d, k):
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=k)).isoformat()


# ---------- series (เติมช่องว่างสั้นๆ ≤ 3 วันด้วยค่าก่อนหน้า) ----------
DATES = sorted(set(d for v in ST.values() for d in v["daily"]))
DATES = [d for d in DATES if d >= "2023-06-01"]


def series(sid, k=0):
    raw = {d: v[k] for d, v in ST[str(sid)]["daily"].items()}
    out, last, age = {}, None, 99
    for d in DATES:
        if d in raw:
            last, age = raw[d], 0
        else:
            age += 1
        if last is not None and age <= 3:
            out[d] = last
    return out


LV = {sid: series(sid) for sid in ST}
NORMAL = {}
for sid, s in LV.items():   # ค่ากลางปกติของแต่ละสถานี = median ทั้งช่วงข้อมูล
    v = sorted(s.values())
    NORMAL[sid] = v[len(v) // 2] if v else 0


def dam(name, i):
    return {d: r[name][i] for d, r in DM.items() if name in r and r[name][i] is not None}


PAS = {k: dam("ป่าสักชลสิทธิ์", i) for k, i in (("pct", 0), ("vol", 1), ("in", 2), ("out", 3), ("normal", 4))}
CPYOUT = {}
for n in CPY_DAMS:
    for d, v in dam(n, 3).items():
        CPYOUT[d] = CPYOUT.get(d, 0) + v
RAIN = RN["obs"]


def rsum(key, d, a, b):
    """ฝนรวมวัน d+a .. d+b"""
    v = [RAIN[key].get(D(d, k)) for k in range(a, b + 1)]
    v = [x for x in v if x is not None]
    return sum(v) if v else None


def moon_spring(d):
    """1 = น้ำเกิด (จันทร์เต็ม/ดับ), 0 = น้ำตาย · รอบ 29.53 วัน"""
    jd = datetime.date.fromisoformat(d).toordinal() + 1721424.5
    f = ((jd - 2451550.26) / 29.530588853) % 1
    return (1 + math.cos(4 * math.pi * f)) / 2


def g(s, d, k=0):
    return s.get(D(d, k)) if k else s.get(d)


def chg(s, d, n, lag=0):
    a, b = g(s, d, -lag), g(s, d, -lag - n)
    return a - b if a is not None and b is not None else None



def solve(A, b):
    """Gaussian elimination (partial pivot)"""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c and M[r][c]:
                k = M[r][c] / M[c][c]
                M[r] = [x - k * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0 for i in range(n)]


def ols(X, y):
    p = len(X[0])
    A = [[sum(r[a] * r[b] for r in X) + (1e-6 if a == b else 0) for b in range(p)] for a in range(p)]
    b = [sum(r[a] * v for r, v in zip(X, y)) for a in range(p)]
    return solve(A, b)


def anom(sid):
    return {d: v - NORMAL[sid] for d, v in LV[sid].items()}


def avg2(a, b):
    return {d: (a[d] + b[d]) / 2 for d in a if d in b}


A = {sid: anom(sid) for sid in LV}
RP = avg2(A["29"], A["36"])     # คลองระพีพัฒน์ แยกตก+แยกใต้
PASOUT = PAS["out"]

# (ชื่อ, series เป้า, ต้นทาง, ช่วง lag, จุดฝน)
# (ชื่อ, series เป้า, ต้นทาง, ช่วง lag, จุดฝน, series ที่ใช้แบ่งช่วงน้ำสูง)
LINKS = {
    "S28": ("S.28 ท้ายเขื่อนป่าสัก", A["2712"], "PASOUT", range(0, 3), "pasak", None),
    "RP": ("คลองระพีพัฒน์", RP, "S28", range(1, 9), "cpylow", "RP"),
    "37": ("ลำลูกกา", A["37"], "RP", range(0, 6), "saimai", "37"),
    "11": ("สายไหม", A["11"], "37", range(0, 3), "saimai", "37"),
}
ORDER = ["S28", "RP", "37", "11"]
HIGH = 0.5   # ม. เหนือปกติ
# เพดานการลดต่อวัน (กำลังสูบ/ระบายของ กทม. มีจำกัด ระดับสูงแค่ไหนก็ลดได้ไม่เกินวันละเท่านี้)
# = quantile ของการลดรายวันจริงช่วงน้ำสูง (> 0.3 ม.) และฝน < 3 มม. · quantile เลือกด้วยการทดสอบย้อนหลัง
CAP_Q = (0.5, 0.75, 0.9, None)


def drop_caps(train_dates, q):
    caps = {}
    for tg in ("11", "37"):
        y, dr = A[tg], []
        for t in train_dates:
            t1 = D(t, 1)
            if t in y and t1 in y and y[t] > 0.3 and RAIN["saimai"].get(t1, 0) < 3:
                dr.append(y[t] - y[t1])
        dr.sort()
        caps[tg] = dr[int(q * (len(dr) - 1))] if (q and len(dr) >= 10) else None
    return caps


def fit_link(key, train_dates, regime=None):
    _, y, src, lags, rk, reg = LINKS[key]
    if regime is None and reg:
        both = {r: fit_link(key, train_dates, r) for r in ("normal", "high")}
        if both["high"]["n"] < 40:          # ข้อมูลน้ำสูงน้อยเกิน ใช้ค่าชุดเดียว
            both["high"] = both["normal"] = fit_link(key, train_dates, "all")
        return {"regimes": both, "lag": both["normal"]["lag"], "n": both["normal"]["n"] + both["high"]["n"]}
    best = None
    for lag in lags:
        X, Y = [], []
        for t in train_dates:
            t1 = D(t, 1)
            x = SERIES[src].get(D(t, -lag))
            if t not in y or t1 not in y or x is None:
                continue
            if regime in ("normal", "high"):
                rv = SERIES[reg].get(t)
                if rv is None or (rv > HIGH) != (regime == "high"):
                    continue
            X.append([y[t], x, RAIN[rk].get(t1, 0), RAIN[rk].get(t, 0), 1.0])
            Y.append(y[t1] - y[t])
        if len(Y) < 12:
            continue
        w = ols(X, Y)
        sse = sum((sum(a * b for a, b in zip(w, r)) - v) ** 2 for r, v in zip(X, Y))
        if best is None or sse / len(Y) < best[1]:
            best = (lag, sse / len(Y), w, len(Y))
    if best is None:
        return {"lag": 0, "k": 0.05, "beta": 0, "r1": 0, "r0": 0, "c": 0, "n": 0}
    lag, mse, w, n = best
    # ข้อจำกัดทางกายภาพ: ต้องลดกลับสู่ปกติ (k>0), ฝนต้องไม่ทำให้ลด
    w[0] = min(w[0], -0.005)
    w[2], w[3] = max(w[2], 0), max(w[3], 0)
    return {"lag": lag, "k": -w[0], "beta": w[1], "r1": w[2], "r0": w[3], "c": w[4], "n": n}


SERIES = {"PASOUT": PASOUT, "S28": A["2712"], "RP": RP, "11": A["11"], "37": A["37"]}



def simulate(params, t0, days, rain_fn, pasout_fn, caps=None):
    """จำลองโซ่ไปข้างหน้า: คืน {key: [a(t0+1) .. a(t0+days)]} · ค่าที่ยังไม่รู้ในอนาคตมาจากการจำลองเอง"""
    cur = {k: dict(SERIES[k]) for k in SERIES}      # สำเนา แล้วเติมค่าที่จำลอง
    for i in range(1, days + 1):
        dt = D(t0, i)
        cur["PASOUT"][dt] = pasout_fn(i)   # ระบาย + ล้น (ถ้ามี) = น้ำที่ออกจากเขื่อนจริง
        for key in ORDER:
            _, _, src, _, rk, reg = LINKS[key]
            p = params[key]
            if "regimes" in p:
                rv = cur[reg].get(D(dt, -1))
                p = p["regimes"]["high" if rv is not None and rv > HIGH else "normal"]
            prev = cur[key].get(D(dt, -1))
            x = cur[src].get(D(dt, -1 - p["lag"]))
            if prev is None or x is None:
                continue
            # แยก "การระบายออก" (ลดกลับสู่ปกติ) กับ "ฝนเติม" เพดานจำกัดเฉพาะการระบาย ฝนยังเติมได้ตามปกติ
            drain = p["k"] * prev - p["beta"] * x - p["c"]
            cap = (caps or {}).get(key)
            if cap is not None and drain > cap:
                drain = cap
            cur[key][dt] = prev - drain + p["r1"] * rain_fn(rk, dt) + p["r0"] * rain_fn(rk, D(dt, -1))
    return {k: [cur[k].get(D(t0, i)) for i in range(1, days + 1)] for k in ("11", "37", "RP", "S28")}


def water_year(d):
    y, mth = int(d[:4]), int(d[5:7])
    return f"{y}/{y + 1}" if mth >= 6 else f"{y - 1}/{y}"


years = sorted(set(water_year(d) for d in DATES))
obs_rain = lambda rk, d: RAIN[rk].get(d, 0)
out = {"built_at": datetime.datetime.now().isoformat(timespec="seconds"), "horizon": HOR, "targets": {}, "links": {}}

# ---------- ทดสอบย้อนหลังแบบจำลอง 14 วัน กันทีละปีน้ำ ----------
def run_cv(capq):
  errs = {t: {"obs": {h: [] for h in range(1, HOR + 1)}, "norain": {h: [] for h in range(1, HOR + 1)},
              "pers": {h: [] for h in range(1, HOR + 1)}, "resid": {h: [] for h in range(1, HOR + 1)},
              # เฉพาะวันเริ่มที่น้ำสูง (เกินปกติ > HIGH_ORIGIN) = สถานการณ์แบบวันนี้
              "obs_hi": {h: [] for h in range(1, HOR + 1)}, "norain_hi": {h: [] for h in range(1, HOR + 1)},
              "pers_hi": {h: [] for h in range(1, HOR + 1)}, "resid_hi": {h: [] for h in range(1, HOR + 1)}} for t in TARGETS}
  HIGH_ORIGIN = 0.3
  for yr in years:
      train = [d for d in DATES if water_year(d) != yr]
      test = [d for d in DATES if water_year(d) == yr]
      if len(test) < 60 or len(train) < 300:
          continue
      params = {k: fit_link(k, train) for k in ORDER}
      caps = drop_caps(train, capq)
      for t0 in test:
          known_out = lambda i, t0=t0: PASOUT.get(D(t0, i), PASOUT.get(t0, 0))
          sims = {"obs": simulate(params, t0, HOR, obs_rain, known_out, caps),
                  "norain": simulate(params, t0, HOR, lambda rk, d, t0=t0: RAIN[rk].get(d, 0) if d <= t0 else 0,
                                     lambda i, t0=t0: PASOUT.get(t0, 0), caps)}
          for tg in TARGETS:
              a0 = A[tg].get(t0)
              if a0 is None:
                  continue
              hi = a0 > HIGH_ORIGIN
              for h in range(1, HOR + 1):
                  truth = A[tg].get(D(t0, h))
                  if truth is None:
                      continue
                  for kind in ("obs", "norain"):
                      v = sims[kind][tg][h - 1]
                      if v is not None:
                          errs[tg][kind][h].append(abs(v - truth))
                          if hi:
                              errs[tg][kind + "_hi"][h].append(abs(v - truth))
                          if kind == "obs":
                              errs[tg]["resid"][h].append(truth - v)
                              if hi:
                                  errs[tg]["resid_hi"][h].append(truth - v)
                  errs[tg]["pers"][h].append(abs(a0 - truth))
                  if hi:
                      errs[tg]["pers_hi"][h].append(abs(a0 - truth))
  return errs


best_cap = None
for q in CAP_Q:
    e = run_cv(q)
    score = sum(sum(e[t]["obs_hi"][h]) / max(1, len(e[t]["obs_hi"][h])) for t in TARGETS for h in (3, 7))
    print(f"  เพดานการลด quantile {q}: MAE น้ำสูง (h3+h7 รวม 2 เป้า) {score * 100:.1f}", flush=True)
    if best_cap is None or score < best_cap[1]:
        best_cap = (q, score, e)
CAPQ, _, errs = best_cap
print("  เลือกเพดาน quantile", CAPQ)

mae = lambda v: round(sum(v) / len(v) * 100, 1) if v else None
params = {k: fit_link(k, DATES) for k in ORDER}
CAPS = drop_caps(DATES, CAPQ)
# ---- ปรับเพดานการลดจากเหตุการณ์ปัจจุบัน (nowcast calibration) ----
# ย้อนพยากรณ์ 26-28 ก.ย. 2569: ช่วงฝนตกโมเดลตามทัน แต่พอฝนหยุด โมเดลให้สายไหมลดวันละ ~20 ซม. ขณะที่จริงลด 8 ซม.
# = ที่ระดับสูงกว่าที่เคยมีในข้อมูล การระบายออกถูกจำกัด (สถานีสูบเต็มกำลัง) ข้อมูลอดีตจึงไม่เห็นผลนี้
# จึงใช้อัตราลดจริงล่าสุดของวันที่ฝนน้อย (< 5 มม.) ในเหตุการณ์นี้เป็นเพดาน ถ้าเป้ายังสูงเกินปกติ > HIGH
# ขอบเขต: ไม่ต่ำกว่า median และไม่เกิน p90 ของการลดช่วงน้ำสูงในอดีต
CAPS_NOW, CAP_NOTE = {}, {}
for tg in TARGETS:
    y = A[tg]
    last_d = max(y)
    hist_caps = {q: drop_caps(DATES, q)[tg] for q in (0.5, 0.9)}
    obs = None
    for i in range(0, 5):     # หา drop ล่าสุดในวันที่ฝนน้อย
        d1, d0 = D(last_d, -i), D(last_d, -i - 1)
        if d1 in y and d0 in y and RAIN["saimai"].get(d1, 0) < 5 and y[d0] > HIGH:
            obs = y[d0] - y[d1]
            break
    if y[last_d] > HIGH and obs is not None and hist_caps[0.5] is not None:
        CAPS_NOW[tg] = min(hist_caps[0.9], max(hist_caps[0.5], obs))
        CAP_NOTE[tg] = f"ลดได้ไม่เกิน {CAPS_NOW[tg] * 100:.0f} ซม./วัน (ลดจริงล่าสุด {obs * 100:.0f} ซม. ในวันฝนน้อย)"
    else:
        CAPS_NOW[tg] = CAPS.get(tg)
        CAP_NOTE[tg] = "ใช้ค่าจากข้อมูลอดีต (ยังไม่มีวันฝนน้อยในเหตุการณ์นี้)"
    print(f"  เพดานเหตุการณ์ {TARGETS[tg]}: {CAP_NOTE[tg]}")
out["drop_cap_now"] = {tg: {"cm_per_day": round(CAPS_NOW[tg] * 100, 1) if CAPS_NOW[tg] else None, "note": CAP_NOTE[tg]} for tg in TARGETS}
out["drop_cap_cm_per_day"] = {k: round(v * 100, 1) if v else None for k, v in CAPS.items()}
out["drop_cap_quantile"] = CAPQ
def describe(p):
    return {"lag": p["lag"], "n": p["n"], "half_life_days": round(math.log(2) / p["k"], 1) if p["k"] > 0 else None,
            "rain_cm_per_mm": round((p["r1"] + p["r0"]) * 100, 2),
            "eq_shift_per_unit_src": round(p["beta"] / p["k"], 3) if p["k"] > 0 else None}


for k, p in params.items():
    regs = p["regimes"] if "regimes" in p else {"all": p}
    out["links"][k] = {"label": LINKS[k][0], "src": LINKS[k][2], "regimes": {r: describe(v) for r, v in regs.items()}}
    for r, v in regs.items():
        dd = describe(v)
        print(f"  {LINKS[k][0]} [{r}]: lag {dd['lag']} ครึ่งชีวิต {dd['half_life_days']} วัน ฝน {dd['rain_cm_per_mm']} ซม./มม. "
              f"ต้นทาง→สมดุล {dd['eq_shift_per_unit_src']} (n={dd['n']})")

# ---------- สถานการณ์ระบายเขื่อนป่าสัก ----------
last = max(DM)
pr = DM[last]["ป่าสักชลสิทธิ์"]
pct0, vol0, inf0, out0, normal0 = pr
inf7 = sum(PAS["in"].get(D(last, -i), inf0) for i in range(7)) / 7
MAXV = 1036.16   # ความจุที่ระดับเก็บกักสูงสุด (RID capacity)


def pasak_path(mode):
    """คืน [(ไหลเข้า, ระบาย, ปริมาตร, ล้น spillway)] 14 วัน ล้าน ลบ.ม. · ไหลเข้าอ่อนลงครึ่งหนึ่งทุก 10 วัน"""
    v, res = vol0, []
    for i in range(1, HOR + 1):
        inf = inf7 * 0.5 ** (i / 10)
        if mode == "hold":        # ระบายเท่าวันนี้
            o = out0
        else:                     # ระบายเท่าที่จำเป็นเพื่อไม่ให้เกินความจุสูงสุดภายใน 14 วัน แต่ไม่ต่ำกว่าวันนี้
            future_in = sum(inf7 * 0.5 ** (j / 10) for j in range(i, HOR + 1))
            o = max(out0, (v + future_in - MAXV * 0.97) / (HOR - i + 1))
        v = v + inf - o
        spill = max(0.0, v - MAXV)     # เกินความจุสูงสุด = ล้นทางระบายน้ำล้น (ไหลออกเองโดยควบคุมไม่ได้)
        v = min(v, MAXV)
        res.append([round(inf, 1), round(o, 1), round(v, 1), round(spill, 1)])
    return res


# แผนระบายตามประกาศกรมชลประทาน 28 ก.ย. 2569 (Thai PBS 558792, ฐานเศรษฐกิจ 670115):
#   30 ก.ย. 115 m³/s · 1 ต.ค. 230 m³/s · 2 ต.ค. 400 m³/s (แม่น้ำป่าสักสูงขึ้น 3.5-4.0 ม.)
# หลังจากนั้นไม่มีประกาศ: สมมติคง 400 m³/s จนปริมาตรกลับถึงระดับเก็บกักปกติ แล้วลดเหลือเท่าน้ำไหลเข้า
RID_PLAN = {"2026-09-30": 115, "2026-10-01": 230, "2026-10-02": 400}
RID_PLAN_SRC = "ประกาศกรมชลประทาน 28 ก.ย. 2569: 30 ก.ย. 115 · 1 ต.ค. 230 · 2 ต.ค. 400 m³/s"


def pasak_rid_plan():
    v, res, last_q = vol0, [], None
    for i in range(1, HOR + 1):
        d = D(last, i)
        inf = inf7 * 0.5 ** (i / 10)
        q = RID_PLAN.get(d, last_q if last_q is not None else out0 * 1e6 / 86400)
        if d > max(RID_PLAN) and v <= normal0:
            q = max(out0 * 1e6 / 86400, inf * 1e6 / 86400)
        last_q = q
        o = q * 86400 / 1e6
        v = v + inf - o
        spill = max(0.0, v - MAXV)
        v = min(v, MAXV)
        res.append([round(inf, 1), round(o, 1), round(v, 1), round(spill, 1)])
    return res


PASAK_SCENARIOS = {"hold": pasak_path("hold"), "release": pasak_rid_plan(), "min_release": pasak_path("release")}
out["pasak"] = {"plan_src": RID_PLAN_SRC, "date": last, "pct": pct0, "volume": vol0, "normal": normal0, "max": MAXV, "inflow": inf0,
                "inflow7": round(inf7, 1), "outflow": out0, "excess_mcm": round(vol0 - normal0, 1),
                "scenarios": PASAK_SCENARIOS}

fc_rain = RN["fc"]
t0 = min(max(d for d in A["11"]), max(d for d in A["37"]))
rain_fc = lambda rk, d: RAIN[rk].get(d, 0) if d <= t0 else fc_rain.get(rk, {}).get(d, 0)
runs = {sc: simulate(params, t0, HOR, rain_fc, lambda i, sc=sc: PASAK_SCENARIOS[sc][i - 1][1] + PASAK_SCENARIOS[sc][i - 1][3], CAPS_NOW)
        for sc in ("hold", "release")}
runs["norain"] = simulate(params, t0, HOR, lambda rk, d: RAIN[rk].get(d, 0) if d <= t0 else 0,
                          lambda i: PASAK_SCENARIOS["release"][i - 1][1], CAPS_NOW)
runs["rain2x"] = simulate(params, t0, HOR, lambda rk, d: rain_fc(rk, d) * (2 if d > t0 else 1),
                          lambda i: PASAK_SCENARIOS["release"][i - 1][1], CAPS_NOW)
runs["fast"] = simulate(params, t0, HOR, rain_fc, lambda i: PASAK_SCENARIOS["release"][i - 1][1], CAPS)   # ลดเร็วแบบอดีต

for tg, label in TARGETS.items():
    y0 = LV[tg][t0]
    e = errs[tg]
    bank = next((f for f in FLAGS if str(f.get("id")) == tg), {})
    fa, fb, fnote = FLOOD_OBS[tg]
    fl_lv = [LV[tg][d] for d in DATES if fa <= d <= fb and d in LV[tg]]
    flood_lv = round(min(fl_lv), 3) if fl_lv else None
    res = {"label": label, "name": ST[tg]["name"], "t0": t0, "cap_note": CAP_NOTE[tg],
           "flood_level": flood_lv, "flood_note": fnote,
           "bank": bank.get("bank"), "ground": bank.get("ground"), "level0": round(y0, 3), "normal": round(NORMAL[tg], 3),
           "max3y_before": round(max(v for d, v in LV[tg].items() if d < "2026-09-01"), 3),
           "hist": [[d, round(LV[tg][d], 3)] for d in DATES if d in LV[tg] and d >= D(t0, -45)],
           "cv": {h: {"obs_rain_cm": mae(e["obs"][h]), "no_rain_cm": mae(e["norain"][h]), "persistence_cm": mae(e["pers"][h]),
                      "n": len(e["pers"][h]),
                      "hi_obs_rain_cm": mae(e["obs_hi"][h]), "hi_no_rain_cm": mae(e["norain_hi"][h]),
                      "hi_persistence_cm": mae(e["pers_hi"][h]), "hi_n": len(e["pers_hi"][h])} for h in range(1, HOR + 1)},
           "h": []}
    for h in range(1, HOR + 1):
        a = runs["release"][tg][h - 1]
        lvl = NORMAL[tg] + a
        rq = sorted(e["resid_hi"][h] if len(e["resid_hi"][h]) >= 30 else e["resid"][h])   # แถบจากสถานการณ์น้ำสูง
        q = lambda p: rq[int(p * (len(rq) - 1))] if rq else 0
        fast = NORMAL[tg] + runs["fast"][tg][h - 1]
        res["h"].append({"h": h, "date": D(t0, h), "level": round(lvl, 3), "dy_cm": round((lvl - y0) * 100, 1),
                         "lo": round(min(lvl, fast) + q(.1), 3), "hi": round(lvl + q(.9), 3), "level_fast": round(fast, 3),
                         "level_hold": round(NORMAL[tg] + runs["hold"][tg][h - 1], 3),
                         "level_norain": round(NORMAL[tg] + runs["norain"][tg][h - 1], 3),
                         "level_rain2x": round(NORMAL[tg] + runs["rain2x"][tg][h - 1], 3),
                         "rain_mm": round(fc_rain.get("saimai", {}).get(D(t0, h), 0), 1)})
    out["targets"][tg] = res
    h7, h14 = res["h"][6], res["h"][13]
    print(f"  {label}: วันนี้ {y0:.2f} ม. → 7 วัน {h7['level']:.2f} ({h7['dy_cm']:+.0f} ซม.) → 14 วัน {h14['level']:.2f} ({h14['dy_cm']:+.0f} ซม.)"
          f" · CV 7 วัน: ฝนจริง {res['cv'][7]['obs_rain_cm']} / ไม่รู้ฝน {res['cv'][7]['no_rain_cm']} / คงที่ {res['cv'][7]['persistence_cm']} ซม."
          f" · เฉพาะน้ำสูง (n={res['cv'][7]['hi_n']}): {res['cv'][7]['hi_obs_rain_cm']} / {res['cv'][7]['hi_no_rain_cm']} / คงที่ {res['cv'][7]['hi_persistence_cm']}")
    for hh in (3, 7, 14):
        c = res["cv"][hh]
        print(f"     h={hh}: น้ำสูง ฝนจริง {c['hi_obs_rain_cm']} ไม่รู้ฝน {c['hi_no_rain_cm']} คงที่ {c['hi_persistence_cm']} ซม. (n={c['hi_n']})")

out["chain_today"] = {k: {"anom": round(SERIES[k].get(t0), 3) if SERIES[k].get(t0) is not None else None,
                          "sim": [round(v, 3) if v is not None else None for v in runs["release"][k]]}
                      for k in ("RP", "S28")}
out["rain_fc"] = {k: v for k, v in fc_rain.items()}
last_dm = DM[last]
out["dams_today"] = {"date": last, "dams": {n: {"pct": r[0], "excess_mcm": round(r[1] - r[4], 1), "inflow": r[2], "outflow": r[3]}
                                            for n, r in last_dm.items() if r[1] is not None and r[4]}}
json.dump(out, open(os.path.join(BASE, "data", "impact_forecast.json"), "w"), ensure_ascii=False, indent=1)
print("OK data/impact_forecast.json")
