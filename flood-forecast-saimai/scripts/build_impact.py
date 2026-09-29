#!/usr/bin/env python3
"""ประกอบ saimai-forecast.html: แอนิเมชัน "14 วันข้างหน้า จะเกิดอะไรกับสายไหม/ลำลูกกา"

ข้อมูล: data/impact_forecast.json (impact_model.py) + บริบทระดับประเทศจาก dams_verified.json,
river_flags.json, geo/upstream.json (เขื่อนและธงภัยทั้งลุ่มเจ้าพระยา)
แผนผัง: ฝน → เขื่อนป่าสัก → ท้ายเขื่อน S.28 → เขื่อนพระรามหก → (เจ้าพระยา | คลองระพีพัฒน์) → ลำลูกกา → สายไหม → สถานีสูบ
คำบรรยายรายวันสร้างจากตัวเลขพยากรณ์ (ไม่เขียนมือ) จึงเปลี่ยนตามข้อมูลทุกครั้งที่ cron รัน"""
import json, os, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = json.load(open(os.path.join(BASE, "data", "impact_forecast.json")))
V = json.load(open(os.path.join(BASE, "data", "dams_verified.json")))
FL = json.load(open(os.path.join(BASE, "data", "river_flags.json")))["flags"]
UP = json.load(open(os.path.join(BASE, "data", "geo", "upstream.json")))
GEO = json.load(open(os.path.join(BASE, "data", "geo", "districts.json")))
RAIN = json.load(open(os.path.join(BASE, "data", "impact", "rain.json")))

THM = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def thd(d):
    y, m, dd = map(int, d.split("-"))
    return f"{dd} {THM[m - 1]}"


def D(d, k):
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=k)).isoformat()


S, L = F["targets"]["11"], F["targets"]["37"]
P = F["pasak"]
t0 = S["t0"]
rain_obs = RAIN["obs"]["saimai"]
rain_fc = F["rain_fc"].get("saimai", {})

# ---------- บริบทระดับประเทศ: ลุ่มเจ้าพระยา ----------
basin = UP["basin"]
geo_idx = {(v["p"], v["a"]): c for c, v in GEO.items()}
BKK = {"กรุงเทพมหานคร", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "สมุทรสาคร", "นครปฐม"}
bcodes = set(basin["codes"])
bflags = [f for f in FL if geo_idx.get((f["pro"], f["amp"])) in bcodes or f["pro"] in BKK]
kflags = [f for f in FL if f["pro"] in BKK]
cpy_dams = [d for d in V["dams"] if d["name"] in basin["dams"]]
nuan = next((f for f in FL if f["name"] == "สะพานนวลฉวี"), None)
ctx = {
    "basin_red": sum(f["sev"] == 2 for f in bflags), "basin_yel": sum(f["sev"] == 1 for f in bflags), "basin_n": len(bflags),
    "bkk_red": sum(f["sev"] == 2 for f in kflags), "bkk_yel": sum(f["sev"] == 1 for f in kflags), "bkk_n": len(kflags),
    "dams": sorted([{"name": d["name"], "pct": d["pct"], "excess": round(d["volume"] - d["normal"], 1) if d["volume"] and d["normal"] else None,
                     "lat": d["lat"]} for d in cpy_dams], key=lambda x: -x["lat"]),
    "nuan_pct": nuan["pct"] if nuan else None,
    "national_over100": [d["name"] for d in V["dams"] if (d["pct"] or 0) > 100],
}

# ---------- คำบรรยายรายวัน (สร้างจากตัวเลข) ----------
rain_before = sum(rain_obs.get(D(t0, -i), 0) for i in range(1, 6))
cap = F["drop_cap_now"]["11"]["cm_per_day"]
rel = P["scenarios"]["release"]
hold = P["scenarios"]["hold"]
spill_day = next((i + 1 for i, x in enumerate(hold) if x[3] > 0), None)
spill_total = round(sum(x[3] for x in hold), 0)
need_rel = rel[0][1]
cap_lvl = [x["level"] for x in S["h"]]
# จุดต่ำแรกก่อนระดับกลับขึ้น (ฝนเติม) และจุดสูงหลังจากนั้น · ถ้าลดตลอด trough = วันสุดท้าย
trough = next((i for i in range(len(cap_lvl) - 1) if cap_lvl[i + 1] > cap_lvl[i]), len(cap_lvl) - 1)
peak_after = max(range(trough, len(cap_lvl)), key=lambda i: cap_lvl[i]) if trough < len(cap_lvl) - 1 else trough

captions = [
    f"<b>วันนี้ {thd(t0)}</b> · ฝนสายไหม 5 วันก่อนหน้ารวม {rain_before:.0f} มม. (25 ก.ย. วันเดียว {rain_obs.get('2026-09-25', 0):.0f} มม.) "
    f"คลองสายไหมสูง <b>{S['level0']:.2f} ม.</b> สูงสุดในรอบ 3 ปี (เดิม {S['max3y_before']:.2f}) · ลำลูกกา <b>{L['level0']:.2f} ม.</b> · "
    f"เขื่อนป่าสัก {P['pct']:.0f}% เกินระดับเก็บกักปกติ {P['excess_mcm']:.0f} ล้าน ลบ.ม. น้ำยังไหลเข้าวันละ ~{P['inflow7']:.0f} ล้าน แต่ระบายแค่ {P['outflow']:.1f}"]
for i, (s_, l_) in enumerate(zip(S["h"], L["h"])):
    day = i + 1
    txt = []
    if day == 1:
        txt.append("กรมชลฯ เริ่มเพิ่มการระบายป่าสัก 115 m³/s ตามประกาศ (ถ้าไม่เพิ่ม อ่างจะเต็มใน ~"
                   f"{spill_day} วัน และล้น spillway ~{spill_total:.0f} ล้าน ลบ.ม.)")
    if day == 2:
        txt.append("ระบาย 230 m³/s · น้ำถึงท้ายเขื่อนในวันเดียว แม่น้ำป่าสักสูงขึ้น → ริมแม่น้ำป่าสัก ท่าเรือ นครหลวง อยุธยา ต้องระวัง (ประกาศทางการ)")
    if day == 3:
        txt.append("ระบาย 400 m³/s · ที่เขื่อนพระรามหก น้ำส่วนใหญ่ (~650 m³/s) ลงแม่น้ำป่าสักถึงเจ้าพระยาที่อยุธยา "
                   "ผันเข้าคลองระพีพัฒน์แค่ ~50 m³/s ตามรายงานวันที่ 28 ก.ย. → ผลต่อสายไหมโดยตรงจึงน้อย")
    fl_s, fl_l = S["flood_level"], L["flood_level"]
    if fl_l and i > 0 and L["h"][i - 1]["level"] >= fl_l > l_["level"]:
        txt.append(f"ลำลูกกาลดต่ำกว่าระดับที่เคยท่วม ({fl_l:.2f} ม.) เป็นครั้งแรก")
    r = s_["rain_mm"]
    if r >= 10:
        txt.append(f"ฝนพยากรณ์ {r:.0f} มม. → คลองสายไหมถูกเติมน้ำกลับ")
    if day == trough + 1 and trough < len(cap_lvl) - 1:
        txt.append(f"สายไหมลดต่ำสุดของช่วงนี้ที่ {s_['level']:.2f} ม. (ลดวันละไม่เกิน ~{cap:.0f} ซม. ตามกำลังระบายที่เห็นจริงในเหตุการณ์นี้)")
    if day == peak_after + 1 and peak_after != trough:
        txt.append(f"หลังฝน สายไหมกลับขึ้นเป็น <b>{s_['level']:.2f} ม.</b> ({(s_['level'] - cap_lvl[trough]) * 100:+.0f} ซม. จากจุดต่ำ) "
                   f"ยังต่ำกว่าวันนี้ {(S['level0'] - s_['level']) * 100:.0f} ซม.")
    if day == len(S["h"]):
        txt.append(f"สิ้นสุด 14 วัน: สายไหม {s_['level']:.2f} ม. ({s_['dy_cm']:+.0f} ซม.) · ลำลูกกา {l_['level']:.2f} ม. ({l_['dy_cm']:+.0f} ซม.) "
                   "ลำลูกกาลดช้ากว่าเพราะผูกกับคลองระพีพัฒน์ที่ยังสูงและลดช้า (ครึ่งชีวิต ~15 วัน)")
    if not txt:
        txt.append(f"สายไหม {s_['level']:.2f} ม. ({s_['dy_cm']:+.0f} ซม.) · ลำลูกกา {l_['level']:.2f} ม. ({l_['dy_cm']:+.0f} ซม.) · "
                   f"ฝน {r:.0f} มม.")
    captions.append(f"<b>วันที่ {day} · {thd(s_['date'])}</b> · " + " · ".join(txt))

DATA = {"f": F, "ctx": ctx, "captions": captions, "rain_obs": {d: rain_obs[d] for d in rain_obs if d >= D(t0, -45)},
        "spill_day": spill_day, "spill_total": spill_total, "trough": trough, "peak_after": peak_after}

HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>สายไหม 14 วันข้างหน้า</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1c1c1a;--sub:#5f5f5a;--mut:#8a8a84;--line:#e4e3de;
--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--t1:#184f95;--t2:#3987e5;--t3:#86b6ef;--water:#3987e5;--ly:#a8a8a2;--link:#256abf}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--card:#1a1a19;--ink:#ededea;--sub:#b5b5ae;
--mut:#85857f;--line:#2e2e2b;--t1:#9ec5f4;--t2:#5598e7;--t3:#256abf;--water:#5598e7;--ly:#6a6a64;--link:#86b6ef}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--ink:#ededea;--sub:#b5b5ae;--mut:#85857f;--line:#2e2e2b;
--t1:#9ec5f4;--t2:#5598e7;--t3:#256abf;--water:#5598e7;--ly:#6a6a64;--link:#86b6ef}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Sarabun","Noto Sans Thai",sans-serif;font-size:15px}
a{color:var(--link)}
.wrap{max-width:1180px;margin:0 auto;padding:14px 16px 40px}
h1{font-size:1.35rem;margin:0}
h2{font-size:1.05rem;margin:22px 0 8px}
.mut{color:var(--mut);font-size:.8rem}.sub{color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:14px 0}
.kpi .v{font-size:1.45rem;font-weight:700;font-variant-numeric:tabular-nums}.kpi .l{font-size:.8rem;color:var(--sub)}
#stage{overflow-x:auto;-webkit-overflow-scrolling:touch}
#stage svg{width:100%;min-width:760px;height:auto;display:block}
@media (max-width:760px){#stage::after{content:"← เลื่อนแผนผังซ้าย-ขวา →";display:block;text-align:center;font-size:.75rem;color:var(--mut)}}
.ctrl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}
.ctrl input[type=range]{flex:1;min-width:180px;accent-color:var(--t1)}
button{font:inherit;font-size:.85rem;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer}
button:hover{border-color:var(--link)}button.on{background:var(--t1);color:#fff;border-color:var(--t1)}
#cap{min-height:64px;margin-top:8px;font-size:.95rem;line-height:1.6;border-left:4px solid var(--t2);padding:4px 12px;background:var(--bg);border-radius:0 8px 8px 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:820px){.two{grid-template-columns:1fr}}
.chart svg{width:100%;height:auto;display:block}
.lgd{font-size:.78rem;color:var(--sub);display:flex;gap:12px;flex-wrap:wrap;margin-top:4px}
.lgd i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:4px}
table{border-collapse:collapse;width:100%;font-size:.84rem}
td,th{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right}
td:first-child,th:first-child{text-align:left}
.flow{animation:flow linear infinite}
@keyframes flow{to{stroke-dashoffset:-24}}
@media (prefers-reduced-motion:reduce){.flow{animation:none}}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:4px 8px;font-size:.78rem;display:none;z-index:5;box-shadow:0 2px 8px rgba(0,0,0,.12)}
</style>
</head>
<body>
<div class="wrap">
<h1>สายไหม · ลำลูกกา: 14 วันข้างหน้าจะเกิดอะไรขึ้น</h1>
<div class="mut" id="stamp"></div>
<div class="kpis" id="kpis"></div>

<div class="card">
  <div id="stage"></div>
  <div class="ctrl">
    <button id="play" class="on">⏸ หยุด</button>
    <button id="prev">◀</button>
    <input type="range" id="day" min="0" max="14" step="0.02" value="0" aria-label="วันที่">
    <button id="next">▶</button>
    <b id="dlabel" style="min-width:130px"></b>
  </div>
  <div id="cap"></div>
</div>

<h2>ระดับน้ำรายวัน: 45 วันที่ผ่านมา + พยากรณ์ 14 วัน</h2>
<div class="two">
  <div class="card chart"><b>สายไหม</b> <span class="mut">คลองลาดพร้าว ท้ายปตร.คลอง2 (ห่างบ้าน 1.9 กม.)</span><div id="c11"></div></div>
  <div class="card chart"><b>ลำลูกกา</b> <span class="mut">คลองหกวา คลอง8</span><div id="c37"></div></div>
</div>
<div class="lgd">
  <span><i style="background:var(--t1)"></i>วัดจริง</span>
  <span><i style="background:var(--t2)"></i>พยากรณ์หลัก (ฝนตามพยากรณ์ Open-Meteo)</span>
  <span><i style="background:var(--t3);height:10px;opacity:.6"></i>ช่วงคาด 10-90%</span>
  <span><i style="background:var(--crit);height:2px"></i>ถ้าฝนมากกว่าพยากรณ์ 2 เท่า</span>
  <span><i style="background:var(--ly);height:2px"></i>ถ้าไม่มีฝนเลย</span>
  <span><i style="border-top:2px dashed var(--crit);height:0"></i>ตลิ่ง ณ จุดวัด</span>
  <span><i style="background:var(--warn);height:3px"></i>ระดับที่ท่วมจริงแล้ว (ช่วงที่มีประกาศ/รายงานท่วม)</span>
  <span>แท่งเทา = ฝนสายไหม (มม.)</span>
</div>

<h2>ตอบคำถามตรงๆ</h2>
<div class="card" id="answers"></div>

<h2>เทียบกับประกาศทางการ (ตรวจ 29 ก.ย. 2569)</h2>
<div class="card" id="official"></div>

<h2>อ้างอิงเขื่อนและธงภัยทั้งลุ่ม</h2>
<div class="two">
  <div class="card" id="ctxd"></div>
  <div class="card" id="ctxf"></div>
</div>

<h2>แบบจำลองทำงานยังไง และแม่นแค่ไหน</h2>
<div class="card" id="model"></div>

<div class="mut" style="margin-top:18px;line-height:1.7">
ข้อมูล: ระดับน้ำ = thaiwater (สสน.) waterlevel_graph ย้อนหลังตั้งแต่ มิ.ย. 2566 · เขื่อน = RID app.rid.go.th รายวัน ·
ฝนย้อนหลัง = Open-Meteo archive (ERA5) · ฝนพยากรณ์ = Open-Meteo 16 วัน · ตลิ่ง = เกณฑ์ min_bank ของสถานี ·
สคริปต์: <code>impact_data.py → impact_model.py → build_impact.py</code> ·
<a href="north-water.html">น้ำเหนือไปไหน (แอนิเมชัน)</a> · <a href="dashboard.html">กลับหน้าเขื่อนทั่วประเทศ</a> · <a href="dashboard-saimai.html">dashboard สายไหมเดิม</a>
</div>
</div>
<div class="tip" id="tip"></div>
<script>
const D = __DATA__;
const F = D.f, S = F.targets['11'], L = F.targets['37'], P = F.pasak, C = D.ctx;
const $ = id => document.getElementById(id);
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const THM = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const thd = d => { const [y, m, dd] = d.split('-').map(Number); return dd + ' ' + THM[m - 1] };
const f0 = v => v == null ? '–' : Math.round(v).toLocaleString('th-TH');
const f2 = v => v == null ? '–' : (+v).toFixed(2);
const sg = v => (v >= 0 ? '+' : '') + Math.round(v);
$('stamp').textContent = 'พยากรณ์จากข้อมูลถึงวันที่ ' + thd(S.t0) + ' · สร้าง ' + F.built_at.replace('T', ' ').slice(0, 16) + ' · อัปเดตทุก 3 ชั่วโมง (cron)';

// ---------- ตัวเลขหลัก ----------
const minS = S.h[D.trough], peakS = S.h[D.peak_after], endS = S.h[S.h.length - 1];
const maxS2 = S.h.reduce((a, b) => b.level_rain2x > a.level_rain2x ? b : a);
$('kpis').innerHTML = [
  [f2(S.level0) + ' ม.', 'สายไหมวันนี้ · <b>ท่วมอยู่แล้ว</b> (ปภ. เตือนคลองหกวาล้นคัน 29 ก.ย.) · สูงสุดในรอบ 3 ปี'],
  [sg(S.h[6].dy_cm) + ' ซม.', 'สายไหมใน 7 วัน (' + f2(S.h[6].level) + ' ม.) · ช่วงคาด ' + f2(S.h[6].lo) + '-' + f2(S.h[6].hi)],
  [sg(L.h[6].dy_cm) + ' ซม.', 'ลำลูกกาใน 7 วัน (' + f2(L.h[6].level) + ' ม.) · ช่วงคาด ' + f2(L.h[6].lo) + '-' + f2(L.h[6].hi)],
  [f0(P.excess_mcm) + ' ล้าน ลบ.ม.', 'ป่าสักเกินระดับเก็บกักปกติ · กรมชลฯ เพิ่มระบายเป็น 400 m³/s (2 ต.ค.) จึงไม่ล้น spillway'],
].map(x => '<div class="card kpi"><div class="v">' + x[0] + '</div><div class="l">' + x[1] + '</div></div>').join('');

// ---------- แผนผังแอนิเมชัน ----------
const W = 1000, H = 470;
const lvlAt = (T, t) => {         // t = วันทศนิยม 0..14 (interpolate)
  const arr = [T.level0].concat(T.h.map(x => x.level)), i = Math.min(13, Math.floor(t)), fr = t - i;
  return arr[i] + (arr[Math.min(14, i + 1)] - arr[i]) * fr;
};
const pasAt = t => { const arr = [[P.inflow7, P.outflow, P.volume, 0]].concat(P.scenarios.release), i = Math.min(13, Math.floor(t)), fr = t - i;
  return arr[i].map((v, k) => v + (arr[Math.min(14, i + 1)][k] - v) * fr) };
const rainAt = t => t < 0.5 ? (D.rain_obs[S.t0] || 0) : (S.h[Math.min(13, Math.max(0, Math.round(t) - 1))].rain_mm || 0);
const rpAt = t => { const a = [F.chain_today.RP.anom].concat(F.chain_today.RP.sim), i = Math.min(13, Math.floor(t)), fr = t - i; return a[i] + (a[Math.min(14, i + 1)] - a[i]) * fr };
const s28At = t => { const a = [F.chain_today.S28.anom].concat(F.chain_today.S28.sim), i = Math.min(13, Math.floor(t)), fr = t - i; return a[i] + (a[Math.min(14, i + 1)] - a[i]) * fr };

function gauge(id, x, y, label, sub) {
  return '<g id="' + id + '" transform="translate(' + x + ',' + y + ')">' +
    '<rect x="0" y="0" width="46" height="150" rx="6" fill="var(--bg)" stroke="var(--ink)" stroke-width="1.5"/>' +
    '<rect class="wat" x="2" y="148" width="42" height="0" rx="4" fill="var(--water)" opacity=".85"/>' +
    '<line class="bank" x1="-6" x2="52" y1="0" y2="0" stroke="var(--crit)" stroke-width="2" stroke-dasharray="4 3"/>' +
    '<line class="today" x1="-4" x2="50" y1="0" y2="0" stroke="var(--ink)" stroke-width="1" opacity=".6"/>' +
    '<line class="flood" x1="-8" x2="54" y1="0" y2="0" stroke="var(--warn)" stroke-width="3"/>' +
    '<text x="23" y="-26" text-anchor="middle" font-size="14" font-weight="700" fill="var(--ink)">' + label + '</text>' +
    '<text x="23" y="-10" text-anchor="middle" font-size="11" fill="var(--mut)">' + sub + '</text>' +
    '<text class="val" x="23" y="172" text-anchor="middle" font-size="15" font-weight="700" fill="var(--ink)"></text>' +
    '<text class="dv" x="23" y="189" text-anchor="middle" font-size="12" fill="var(--sub)"></text></g>';
}
let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="แผนผังการไหลของน้ำ จากเขื่อนป่าสักถึงสายไหม">';
svg += '<defs><marker id="ah" viewBox="0 0 10 10" refX="7" refY="5" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="var(--t2)"/></marker></defs>';
// แถวหลัก y≈100-250: ป่าสัก(30) → S.28(235) → พระรามหก(360) → ระพีพัฒน์(505) → ลำลูกกา(700) → สายไหม(875)
const paths = {
  pas: 'M142 175 L228 175', s28: 'M284 175 L354 175', rp: 'M410 175 L498 175', llk: 'M554 175 L692 175',
  sm: 'M748 175 L866 175', cpy: 'M384 212 L384 400 L500 400', pump: 'M898 330 L898 420',
};
Object.entries(paths).forEach(([k, d]) => {
  svg += '<path d="' + d + '" fill="none" stroke="var(--line)" stroke-width="12" stroke-linecap="round"/>';
  svg += '<path id="p_' + k + '" d="' + d + '" fill="none" stroke="var(--t2)" stroke-width="4" stroke-dasharray="8 16" class="flow" marker-end="url(#ah)"/>';
});
svg += '<text x="620" y="164" text-anchor="middle" font-size="11" fill="var(--sub)">คลองรังสิต/คลองหกวา</text>';
svg += '<text x="808" y="164" text-anchor="middle" font-size="11" fill="var(--sub)">คลองหกวา</text>';
// เขื่อนป่าสัก (ถังน้ำ)
svg += '<g transform="translate(30,100)"><rect x="0" y="0" width="110" height="140" rx="8" fill="var(--bg)" stroke="var(--ink)" stroke-width="1.5"/>' +
  '<rect id="pasw" x="2" y="138" width="106" height="0" rx="6" fill="var(--water)" opacity=".85"/>' +
  '<line id="pasn" x1="-6" x2="116" stroke="var(--warn)" stroke-width="2" stroke-dasharray="5 3"/>' +
  '<line id="pasm" x1="-6" x2="116" stroke="var(--crit)" stroke-width="2" stroke-dasharray="5 3"/>' +
  '<text x="55" y="-26" text-anchor="middle" font-size="14" font-weight="700" fill="var(--ink)">เขื่อนป่าสักชลสิทธิ์</text>' +
  '<text x="55" y="-10" text-anchor="middle" font-size="11" fill="var(--mut)">เส้นส้ม = รนก. · แดง = สูงสุด</text>' +
  '<text id="pasv" x="55" y="162" text-anchor="middle" font-size="15" font-weight="700" fill="var(--ink)"></text>' +
  '<text id="pasf" x="55" y="179" text-anchor="middle" font-size="11" fill="var(--sub)"></text>' +
  '<text id="pass" x="55" y="195" text-anchor="middle" font-size="11" fill="var(--crit)"></text></g>';
svg += gauge('g28', 235, 100, 'S.28', 'ท้ายเขื่อน');
svg += '<g transform="translate(356,140)"><rect width="54" height="70" rx="6" fill="var(--card)" stroke="var(--ink)" stroke-width="1.5"/>' +
  '<text x="27" y="-10" text-anchor="middle" font-size="13" font-weight="700" fill="var(--ink)">พระรามหก</text>' +
  '<text x="27" y="40" text-anchor="middle" font-size="11" fill="var(--sub)">แบ่งน้ำ</text></g>';
svg += '<g transform="translate(508,392)"><text font-size="13" font-weight="700" fill="var(--ink)">แม่น้ำป่าสัก → เจ้าพระยา (อยุธยา → กทม.)</text>' +
  '<text y="18" font-size="11" fill="var(--sub)" id="cpytxt"></text><text y="34" font-size="11" fill="var(--sub)">น้ำส่วนใหญ่ที่ระบายจากป่าสักไปทางนี้ ไม่ใช่เข้าคลอง</text></g>';
svg += gauge('grp', 500, 100, 'คลองระพีพัฒน์', 'แยกตก/แยกใต้');
svg += gauge('gllk', 695, 100, 'ลำลูกกา', 'คลองหกวา คลอง8');
svg += gauge('gsm', 870, 100, 'สายไหม', 'ท้ายปตร.คลอง2');
svg += '<g transform="translate(810,300)"><path d="M0 16 L14 4 L28 16 V32 H0 Z" fill="var(--card)" stroke="var(--ink)" stroke-width="1.5"/>' +
  '<text x="14" y="50" text-anchor="middle" font-size="11" fill="var(--ink)" font-weight="700">บ้าน</text></g>';
svg += '<text x="912" y="444" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ink)">สถานีสูบ/ระบายออก</text>' +
  '<text id="pumpt" x="912" y="460" text-anchor="middle" font-size="11" fill="var(--sub)"></text>';
svg += '<g id="cloud" transform="translate(720,6)"><ellipse cx="90" cy="26" rx="80" ry="20" fill="var(--ly)" opacity=".8"/>' +
  '<ellipse cx="40" cy="28" rx="38" ry="15" fill="var(--ly)" opacity=".8"/><text id="raint" x="90" y="31" text-anchor="middle" font-size="13" font-weight="700" fill="var(--ink)"></text>' +
  '<g id="drops"></g></g>';
svg += '</svg>';
$('stage').innerHTML = svg;
const st = $('stage').querySelector('svg');
// gauge scale: ระดับ (ม.รทก.) → พิกเซล
function scaleFor(lo, hi) { return v => 148 - Math.max(0, Math.min(1, (v - lo) / (hi - lo))) * 146 }
const G = {
  gsm: {T: S, sc: scaleFor(-0.3, S.bank + 0.3)}, gllk: {T: L, sc: scaleFor(-0.3, L.bank + 0.3)},
};
Object.entries(G).forEach(([id, g]) => {
  const el = st.querySelector('#' + id);
  el.querySelector('.bank').setAttribute('y1', g.sc(g.T.bank)); el.querySelector('.bank').setAttribute('y2', g.sc(g.T.bank));
  el.querySelector('.today').setAttribute('y1', g.sc(g.T.level0)); el.querySelector('.today').setAttribute('y2', g.sc(g.T.level0));
  el.querySelector('.flood').setAttribute('y1', g.sc(g.T.flood_level)); el.querySelector('.flood').setAttribute('y2', g.sc(g.T.flood_level));
});
['g28', 'grp'].forEach(id => { const el = st.querySelector('#' + id); el.querySelector('.bank').style.display = 'none';
  el.querySelector('.flood').style.display = 'none';
  el.querySelector('.today').style.display = 'none' });
const pv = v => 138 - Math.max(0, Math.min(1, v / (P.max * 1.03))) * 136;
st.querySelector('#pasn').setAttribute('y1', pv(P.normal)); st.querySelector('#pasn').setAttribute('y2', pv(P.normal));
st.querySelector('#pasm').setAttribute('y1', pv(P.max)); st.querySelector('#pasm').setAttribute('y2', pv(P.max));

function setGauge(id, y, txt, dtxt) {
  const el = st.querySelector('#' + id), w = el.querySelector('.wat');
  w.setAttribute('y', y); w.setAttribute('height', Math.max(0, 148 - y));
  el.querySelector('.val').textContent = txt; el.querySelector('.dv').textContent = dtxt;
}
function speed(id, mag) {       // ความเร็ว/ความหนาเส้นไหลตามปริมาณ
  const p = st.querySelector('#p_' + id); if (!p) return;
  const m = Math.max(0, Math.min(1, mag));
  p.style.animationDuration = (2.6 - 2.1 * m) + 's';
  p.setAttribute('stroke-width', 2 + 5 * m);
  p.style.opacity = .25 + .75 * m;
}
let T = 0;
function render(t) {
  T = t;
  const day = Math.round(t), date = day === 0 ? S.t0 : S.h[day - 1].date;
  $('dlabel').textContent = (day === 0 ? 'วันนี้ ' : 'วันที่ ' + day + ' · ') + thd(date);
  $('day').value = t;
  // เขื่อนป่าสัก
  const [inf, out, vol, spill] = pasAt(t);
  const pw = st.querySelector('#pasw'); pw.setAttribute('y', pv(vol)); pw.setAttribute('height', 138 - pv(vol));
  st.querySelector('#pasv').textContent = f0(vol / P.normal * 100) + '% · ' + f0(vol) + ' ล้าน';
  st.querySelector('#pasf').textContent = 'เข้า ' + f0(inf) + ' / ระบาย ' + f0(out) + ' ล้าน/วัน';
  st.querySelector('#pass').textContent = 'เกิน รนก. ' + f0(vol - P.normal) + ' · ความจุสูงสุด ' + f0(P.max);
  speed('pas', out / 35); speed('s28', out / 35); speed('cpy', out / 35);
  speed('rp', 0.15);   // ผันเข้าระพีพัฒน์ ~50 m³/s คงที่ตามรายงาน (น้อยเมื่อเทียบกับที่ลงเจ้าพระยา)
  // S.28, ระพีพัฒน์ (ระดับเทียบปกติ)
  const s28 = s28At(t), rp = rpAt(t);
  setGauge('g28', 148 - Math.max(0, Math.min(1, (s28 + 1) / 6)) * 146, sg(s28 * 100) + ' ซม.', 'เทียบปกติ');
  setGauge('grp', 148 - Math.max(0, Math.min(1, (rp + 0.5) / 2.5)) * 146, sg(rp * 100) + ' ซม.', 'เทียบปกติ');
  st.querySelector('#cpytxt').textContent = 'ท้ายเขื่อนป่าสัก S.28 ' + sg(s28 * 100) + ' ซม. เหนือปกติ';
  // ลำลูกกา / สายไหม
  const lv = lvlAt(L, t), sv = lvlAt(S, t);
  const fl = (v, T) => v >= T.flood_level ? '⚠ เกินระดับท่วม ' + sg((v - T.flood_level) * 100) + ' ซม.' : 'ต่ำกว่าระดับท่วม ' + f0((T.flood_level - v) * 100) + ' ซม.';
  setGauge('gllk', G.gllk.sc(lv), f2(lv) + ' ม. (' + sg((lv - L.level0) * 100) + ')', fl(lv, L));
  setGauge('gsm', G.gsm.sc(sv), f2(sv) + ' ม. (' + sg((sv - S.level0) * 100) + ')', fl(sv, S));
  speed('llk', (lv - L.normal) / 1.5); speed('sm', (sv - S.normal) / 1.5);
  const drain = Math.min(F.drop_cap_now['11'].cm_per_day || 8, Math.max(0, (sv - S.normal) * 100 * 0.2));
  speed('pump', drain / 10);
  st.querySelector('#pumpt').textContent = 'ระบายได้ ≲ ' + f0(F.drop_cap_now['11'].cm_per_day) + ' ซม./วัน (เต็มกำลัง)';
  // ฝน
  const r = rainAt(t);
  st.querySelector('#raint').textContent = 'ฝน ' + f0(r) + ' มม.';
  let dr = ''; const n = Math.min(14, Math.round(r / 2));
  for (let i = 0; i < n; i++) { const x = 20 + (i * 97 % 140), y0 = 44 + ((i * 37 + Math.round(t * 60)) % 36);
    dr += '<line x1="' + x + '" y1="' + y0 + '" x2="' + (x - 3) + '" y2="' + (y0 + 9) + '" stroke="var(--water)" stroke-width="2" stroke-linecap="round"/>' }
  st.querySelector('#drops').innerHTML = dr;
  $('cap').innerHTML = D.captions[day];
  drawCharts(t);
}

// ---------- กราฟ ----------
function chart(el, T, t) {
  const hist = T.hist, fc = T.h, W2 = 520, H2 = 230, L0 = 40, R0 = 10, T0 = 10, B0 = 42;
  const UT = s => Date.parse(s + 'T00:00:00Z');
  const x0 = UT(hist[0][0]), x1 = UT(fc[fc.length - 1].date);
  const vals = hist.map(p => p[1]).concat(fc.flatMap(p => [p.lo, p.hi, p.level_rain2x, p.level_norain]), [T.bank]);
  const lo = Math.floor(Math.min(...vals) * 2) / 2, hi = Math.ceil(Math.max(...vals) * 2) / 2 + .1;
  const X = d => L0 + (UT(d) - x0) / (x1 - x0) * (W2 - L0 - R0), Y = v => T0 + (hi - v) / (hi - lo) * (H2 - T0 - B0);
  let g = '';
  for (let v = lo; v <= hi; v += .5) g += '<line x1="' + L0 + '" x2="' + (W2 - R0) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="var(--line)"/>' +
    '<text x="' + (L0 - 4) + '" y="' + (Y(v) + 4) + '" font-size="10" text-anchor="end" fill="var(--mut)">' + v.toFixed(1) + '</text>';
  // ฝน (แท่ง ด้านล่าง)
  const rmax = 130, RB = H2 - 20;
  Object.entries(D.rain_obs).forEach(([d, r]) => { if (UT(d) < x0 || !r) return;
    g += '<rect x="' + (X(d) - 2) + '" y="' + (RB - r / rmax * 30) + '" width="4" height="' + (r / rmax * 30) + '" fill="var(--ly)"/>' });
  fc.forEach(p => { if (p.rain_mm) g += '<rect x="' + (X(p.date) - 2) + '" y="' + (RB - p.rain_mm / rmax * 30) + '" width="4" height="' + (p.rain_mm / rmax * 30) + '" fill="var(--t3)"/>' });
  g += '<text x="' + (W2 - R0) + '" y="' + (H2 - 4) + '" font-size="10" text-anchor="end" fill="var(--mut)">ฝน (มม.)</text>';
  hist.forEach(p => { if (p[0].slice(8) === '01') g += '<text x="' + X(p[0]) + '" y="' + (H2 - 26) + '" font-size="10" text-anchor="middle" fill="var(--mut)">' + THM[+p[0].slice(5, 7) - 1] + '</text>' });
  // ตลิ่ง
  g += '<line x1="' + L0 + '" x2="' + (W2 - R0) + '" y1="' + Y(T.bank) + '" y2="' + Y(T.bank) + '" stroke="var(--crit)" stroke-dasharray="5 3"/>' +
    '<text x="' + (L0 + 4) + '" y="' + (Y(T.bank) - 4) + '" font-size="10" fill="var(--crit)">ตลิ่ง ' + T.bank.toFixed(2) + ' ม.</text>';
  if (T.flood_level) g += '<line x1="' + L0 + '" x2="' + (W2 - R0) + '" y1="' + Y(T.flood_level) + '" y2="' + Y(T.flood_level) + '" stroke="var(--warn)" stroke-width="2.5"/>' +
    '<text x="' + (L0 + 4) + '" y="' + (Y(T.flood_level) - 4) + '" font-size="10" font-weight="700" fill="var(--ink)">ระดับที่ท่วมจริง ' + T.flood_level.toFixed(2) + ' ม. (ตามประกาศ)</text>';
  // แถบ + เส้นพยากรณ์
  const start = [T.t0, T.level0];
  const band = [[T.t0, T.level0]].concat(fc.map(p => [p.date, p.hi])).map(p => X(p[0]) + ' ' + Y(p[1]))
    .concat([[T.t0, T.level0]].concat(fc.map(p => [p.date, p.lo])).reverse().map(p => X(p[0]) + ' ' + Y(p[1])));
  g += '<path d="M' + band.join('L') + 'Z" fill="var(--t3)" opacity=".35"/>';
  const line = (k, col, dash, w) => '<path d="M' + [start].concat(fc.map(p => [p.date, p[k]])).map(p => X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('L') +
    '" fill="none" stroke="' + col + '" stroke-width="' + w + '"' + (dash ? ' stroke-dasharray="' + dash + '"' : '') + '/>';
  g += line('level_norain', 'var(--ly)', '4 3', 1.5) + line('level_rain2x', 'var(--crit)', '4 3', 1.5) + line('level', 'var(--t2)', '6 3', 2.5);
  g += '<path d="M' + hist.map(p => X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('L') + '" fill="none" stroke="var(--t1)" stroke-width="2.2"/>';
  // วันปัจจุบันของแอนิเมชัน
  const day = Math.round(t), d = day === 0 ? T.t0 : fc[day - 1].date, v = day === 0 ? T.level0 : fc[day - 1].level;
  g += '<line x1="' + X(d) + '" x2="' + X(d) + '" y1="' + T0 + '" y2="' + (H2 - B0) + '" stroke="var(--ink)" stroke-width="1.2"/>' +
    '<circle cx="' + X(d) + '" cy="' + Y(v) + '" r="5" fill="var(--card)" stroke="var(--ink)" stroke-width="2"/>' +
    '<text x="' + Math.min(W2 - 60, X(d) + 8) + '" y="' + (Y(v) - 8) + '" font-size="12" font-weight="700" fill="var(--ink)">' + v.toFixed(2) + ' ม.</text>';
  el.innerHTML = '<svg viewBox="0 0 ' + W2 + ' ' + H2 + '">' + g + '</svg>';
}
function drawCharts(t) { chart($('c11'), S, t); chart($('c37'), L, t) }

// ---------- คำตอบ ----------
const up11 = S.h.reduce((m, p) => Math.max(m, p.level - S.level0), -9), up37 = L.h.reduce((m, p) => Math.max(m, p.level - L.level0), -9);
const over = (T, k) => T.h.filter(p => p[k] >= T.flood_level).length;
const firstBelow = T => { const p = T.h.find(p => p.level < T.flood_level); return p ? thd(p.date) : 'หลัง 14 วัน' };
const gap = T => Math.min(...T.h.map(p => T.flood_level - p.level));
$('answers').innerHTML =
  '<p style="padding:8px 12px;border-left:4px solid var(--warn);background:var(--bg);border-radius:0 8px 8px 0"><b>สรุปสั้น: ไม่ขัดกับประกาศทางการ</b> · ' +
  'สายไหมและลำลูกกา<b>ท่วมอยู่แล้วตอนนี้</b> สาเหตุหลักคือฝนหนัก 25-28 ก.ย. (258 มม. ใน 5 วัน) จนคลองหกวาล้นคัน ไม่ใช่น้ำจากเขื่อน · ' +
  'พยากรณ์บอกว่าน้ำ<b>ค่อยๆ ลด แต่ช้า</b> ไม่ได้บอกว่าปลอดภัย · ส่วนประกาศเรื่องน้ำจากเขื่อนป่าสัก/เจ้าพระยา เป็นของ<b>พื้นที่ริมแม่น้ำนอกคันกั้นน้ำ</b> ซึ่งหน้านี้ไม่ได้พยากรณ์</p>' +
  '<p><b>1) น้ำล้นเขื่อนมากแค่ไหน?</b> ป่าสัก ' + f0(P.pct) + '% เกินระดับเก็บกักปกติ ' + f0(P.excess_mcm) + ' ล้าน ลบ.ม. ยังไม่ล้น spillway (รับได้ถึง ' + f0(P.max) + ') · ' +
  'กรมชลฯ ประกาศเพิ่มระบาย 115 → 230 → <b>400 m³/s</b> (30 ก.ย. - 2 ต.ค.) แม่น้ำป่าสักจะสูงขึ้น 3.5-4 ม. · ถ้าไม่เพิ่ม จะเต็มใน ~' + D.spill_day +
  ' วันแล้วล้น ~' + f0(D.spill_total) + ' ล้าน ลบ.ม. · น้ำนี้ไปทาง<b>แม่น้ำป่าสัก → อยุธยา → เจ้าพระยา</b> เป็นหลัก เขื่อนพระรามหกผันเข้าคลองระพีพัฒน์แค่ ~50 จาก ~700 m³/s</p>' +
  '<p><b>2) สายไหมจะสูงขึ้นอีกกี่ ซม.?</b> พยากรณ์หลัก: ไม่สูงเกินวันนี้ (' + f2(S.level0) + ' ม. = ระดับที่ ปภ. เตือนว่าคลองล้นคัน) · ลดวันละไม่เกิน ~' +
  f0(F.drop_cap_now['11'].cm_per_day) + ' ซม. ถึง ' + f2(minS.level) + ' ม. (' + thd(minS.date) + ')' +
  (D.peak_after > D.trough ? ' แล้วฝนพยากรณ์ดันกลับขึ้นเป็น ' + f2(peakS.level) + ' ม. (' + thd(peakS.date) + ')' : '') +
  ' · ตลอด 14 วัน<b>อยู่ต่ำกว่าระดับท่วมแค่ ' + f0(gap(S) * 100) + '-' + f0((S.flood_level - endS.level) * 100) + ' ซม.</b> = ยังเสี่ยงสูง · ' +
  '<b>ถ้าฝนมากกว่าพยากรณ์ 2 เท่า</b> จะขึ้นถึง ' + f2(maxS2.level_rain2x) + ' ม. (' + sg((maxS2.level_rain2x - S.level0) * 100) + ' ซม. จากวันนี้) และเกินระดับท่วม ' +
  over(S, 'level_rain2x') + ' จาก 14 วัน</p>' +
  '<p><b>3) ลำลูกกา?</b> ยังอยู่<b>เหนือระดับที่ท่วม (' + f2(L.flood_level) + ' ม.) อีก ' + over(L, 'level') + ' วัน</b> ต่ำกว่าครั้งแรกประมาณ ' + firstBelow(L) +
  ' · ลดช้าเพราะผูกกับคลองระพีพัฒน์ที่ยังสูงเหนือปกติ ~' + f0(F.chain_today.RP.anom * 100) + ' ซม. · 7 วัน ' + sg(L.h[6].dy_cm) + ' ซม. · 14 วัน ' + sg(L.h[13].dy_cm) + ' ซม.</p>';

// ---------- เทียบประกาศทางการ ----------
$('official').innerHTML = '<table><tr><th>ประกาศ</th><th>พื้นที่</th><th>หน้านี้ครอบคลุม?</th></tr>' +
  [['ปภ. 29 ก.ย.: เขตสายไหม คลองสามวา หนองจอก "คลองหกวาสายล่างล้นคันกั้นน้ำ"', 'คลองในเขตบ้าน', '✓ ตรงกัน: ระดับวันนี้ = ระดับที่เตือน พยากรณ์ยังค้างใกล้ระดับนี้ 2 สัปดาห์'],
   ['ลำลูกกาท่วม 40-70 ซม. (25-27 ก.ย.) จากฝนหนักจนคลองล้นตลิ่ง', 'ลำลูกกา คูคต', '✓ ตรงกัน: ลำลูกกายังเหนือระดับท่วมอีก ~' + over(L, 'level') + ' วัน'],
   ['กรมชลฯ 28 ก.ย.: ป่าสักระบาย 115 → 230 → 400 m³/s แม่น้ำป่าสักสูงขึ้น 3.5-4 ม.', 'ริมแม่น้ำป่าสัก ท่าเรือ นครหลวง อยุธยา', '◐ ใช้แผนนี้ในโมเดล แต่ไม่ได้พยากรณ์ระดับริมแม่น้ำป่าสัก'],
   ['ธงแดงเขื่อนพระรามหก: น้ำเข้า ~700 m³/s ผันเข้าระพีพัฒน์ ~50 m³/s ล้นคันนอกแนวป้องกันแล้ว', 'ริมแม่น้ำป่าสักใต้พระรามหก', '◐ ยืนยันข้อค้นพบของโมเดล (ผันเข้าคลองน้อย) แต่ไม่ได้พยากรณ์ริมแม่น้ำ'],
   ['กรมชลฯ/กทม.: เจ้าพระยาสูงขึ้น 0.6-1.5 ม. (เขื่อนเจ้าพระยาระบาย 700-1,850 m³/s)', 'ชุมชนริมเจ้าพระยานอกคันกั้นน้ำ 11 จังหวัด + กทม.', '✗ ไม่ครอบคลุม ต้องติดตามประกาศโดยตรง']]
  .map(r => '<tr><td style="text-align:left">' + r[0] + '</td><td style="text-align:left">' + r[1] + '</td><td style="text-align:left">' + r[2] + '</td></tr>').join('') + '</table>' +
  '<p class="mut">ที่มา: <a href="https://www.bangkokbiznews.com/news/news-update/1254210">กรุงเทพธุรกิจ (ปภ. เตือน 3 เขต)</a> · ' +
  '<a href="https://www.dailynews.co.th/news/6227194/">เดลินิวส์ (ลำลูกกา)</a> · <a href="https://www.thaipbs.or.th/news/content/558792">Thai PBS (แผนระบายป่าสัก)</a> · ' +
  '<a href="https://www.khaosodenglish.com/news/2026/09/28/rama-vi-dam-raises-red-flag-as-pasak-river-levels-rise/">Khaosod English (พระรามหก)</a> · ' +
  '<a href="https://www.nationthailand.com/news/general/40071311">Nation (เจ้าพระยา กทม.)</a> · <a href="https://www.nationthailand.com/news/general/40071518">Nation (1,850 m³/s)</a> · ' +
  'ถ้าข้อความทางการกับหน้านี้ต่างกัน <b>ให้เชื่อประกาศทางการ</b> (หน่วยงานรู้แผนเปิด-ปิดประตูน้ำที่โมเดลไม่รู้)</p>';

// ---------- บริบทลุ่ม ----------
$('ctxd').innerHTML = '<b>10 เขื่อนลุ่มเจ้าพระยา (เหนือ → ใต้)</b><table><tr><th>เขื่อน</th><th>% ความจุ</th><th>เกิน รนก. (ล้าน ลบ.ม.)</th></tr>' +
  C.dams.map(d => '<tr><td>' + d.name + '</td><td>' + (d.pct == null ? '–' : d.pct.toFixed(1)) + '</td><td>' +
    (d.excess > 0 ? '<b style="color:var(--crit)">+' + f0(d.excess) + '</b>' : f0(d.excess)) + '</td></tr>').join('') + '</table>';
$('ctxf').innerHTML = '<b>ธงภัยวันนี้</b><table><tr><th>พื้นที่</th><th>สถานี</th><th>แดง</th><th>เหลือง</th></tr>' +
  '<tr><td>ลุ่มเจ้าพระยาทั้งลุ่ม + กทม.</td><td>' + C.basin_n + '</td><td>' + C.basin_red + '</td><td>' + C.basin_yel + '</td></tr>' +
  '<tr><td>กทม. และปริมณฑล</td><td>' + C.bkk_n + '</td><td>' + C.bkk_red + '</td><td>' + C.bkk_yel + '</td></tr></table>' +
  '<p class="sub" style="font-size:.85rem">เจ้าพระยาที่สะพานนวลฉวี ' + f0(C.nuan_pct) + '% ของตลิ่ง: แม่น้ำสูง ทำให้คลองฝั่ง กทม. ระบายลงแม่น้ำได้ช้า ' +
  '(รวมอยู่ในอัตราลดที่วัดจริงของเหตุการณ์นี้)</p>';

// ---------- โมเดล ----------
const cvr = (T, h) => T.cv[h];
const row = (T, h) => { const c = cvr(T, h); return '<tr><td>' + T.label + ' ' + h + ' วัน</td><td>' + c.hi_obs_rain_cm + '</td><td>' + c.hi_no_rain_cm + '</td><td>' + c.hi_persistence_cm + '</td><td>' + c.hi_n + '</td></tr>' };
const lk = F.links;
$('model').innerHTML = '<p>โซ่ "linear reservoir" รายวัน เรียนค่าจากข้อมูลจริง มิ.ย. 2566 - วันนี้: ' +
  '<b>เขื่อนป่าสัก → ท้ายเขื่อน S.28 → คลองระพีพัฒน์ → ลำลูกกา → สายไหม</b> · ทุกข้อต่อ: ระดับลดกลับสู่ปกติด้วยอัตราคงที่ + แรงดันจากต้นทาง + ฝน · ' +
  'แยกค่าช่วงน้ำปกติ/น้ำสูง · เพดานการระบายต่อวันปรับจากอัตราลดจริงของเหตุการณ์นี้ทุกครั้งที่อัปเดต</p>' +
  '<table><tr><th>ข้อต่อ (ช่วงน้ำสูง)</th><th>ครึ่งชีวิตการลด</th><th>ฝน ซม./มม.</th><th>ต้นทางดันระดับ</th></tr>' +
  ['RP', '37', '11'].map(k => { const r = lk[k].regimes.high || lk[k].regimes.all;
    return '<tr><td>' + lk[k].label + ' ← ' + ({S28: 'S.28', RP: 'ระพีพัฒน์', '37': 'ลำลูกกา'})[lk[k].src] + '</td><td>' + r.half_life_days + ' วัน</td><td>' + r.rain_cm_per_mm +
      '</td><td>' + r.eq_shift_per_unit_src + ' ม./ม.</td></tr>' }).join('') + '</table>' +
  '<p style="margin-top:12px"><b>ทดสอบย้อนหลัง</b> จำลอง 14 วันจริง กันข้อมูลทีละปีน้ำ · เฉพาะวันเริ่มที่น้ำสูงเกินปกติ > 30 ซม. (สถานการณ์แบบวันนี้) · ความคลาดเคลื่อนเฉลี่ย (ซม.)</p>' +
  '<table><tr><th>เป้า</th><th>รู้ฝนจริง</th><th>ไม่รู้ฝน</th><th>ถือว่าเท่าเดิม</th><th>จำนวน</th></tr>' +
  [3, 7, 14].map(h => row(S, h)).join('') + [3, 7, 14].map(h => row(L, h)).join('') + '</table>' +
  '<p class="sub" style="font-size:.86rem">อ่านผล: สายไหม 3-7 วันแม่นกว่า "ถือว่าเท่าเดิม" ~30% <b>ถ้าพยากรณ์ฝนแม่น</b> ถ้าไม่รู้ฝนแทบไม่ดีกว่า · ' +
  'ลำลูกกาแม่นกว่าชัดที่ 14 วัน · 14 วันของสายไหมไม่แม่นกว่าการเดา จึงแสดงแถบกว้าง · ' +
  'ระดับวันนี้สูงกว่าข้อมูลฝึกทั้งหมด (เดิมสูงสุด ' + f2(S.max3y_before) + ' ม.) ตัวเลขจึงเป็น<b>การคาดการเชิงสถิติ</b> ไม่ใช่คำเตือนทางการ · ' +
  'ไม่รู้แผนเปิด-ปิดประตูน้ำ/สูบน้ำของ กทม. และแผนผันน้ำของกรมชลฯ</p>';

// ---------- เล่น ----------
let playing = true, last = null;
function tick(ts) {
  if (playing) {
    if (last != null) T += (ts - last) / 1400;     // 1 วัน ≈ 1.4 วินาที
    if (T > 14) { T = 14; playing = false; $('play').textContent = '▶ เล่นใหม่'; $('play').classList.remove('on') }
    render(T);
  }
  last = ts; requestAnimationFrame(tick);
}
$('play').onclick = () => { if (!playing && T >= 14) T = 0; playing = !playing;
  $('play').textContent = playing ? '⏸ หยุด' : '▶ เล่น'; $('play').classList.toggle('on', playing) };
$('day').oninput = () => { playing = false; $('play').textContent = '▶ เล่น'; $('play').classList.remove('on'); render(+$('day').value) };
$('prev').onclick = () => { playing = false; render(Math.max(0, Math.ceil(T) - 1)) };
$('next').onclick = () => { playing = false; render(Math.min(14, Math.floor(T) + 1)) };
if (matchMedia('(prefers-reduced-motion: reduce)').matches) { playing = false; $('play').textContent = '▶ เล่น' }
render(0); requestAnimationFrame(tick);
</script>
</body></html>
"""

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
out = os.path.join(BASE, "saimai-forecast.html")
open(out, "w").write(html)
print("OK", out, f"size={len(html.encode()) / 1e3:.0f} KB")
