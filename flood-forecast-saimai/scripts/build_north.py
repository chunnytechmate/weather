#!/usr/bin/env python3
"""ประกอบ north-water.html: แอนิเมชัน "น้ำเหนือไปไหน ทำไมไม่ทำให้สายไหมท่วมเพิ่ม และใครได้รับผลจริง"

7 ฉาก บนแผนที่ลำน้ำจริงลุ่มเจ้าพระยา (HydroRIVERS แยกสายโดย north_prep.py):
  1 ฝน 25-28 ก.ย. · 2 เขื่อนใหญ่รับน้ำไว้ · 3 น้ำก้อนนี้มาจากปิงตอนล่าง+ยม (ที่มาของ +50%)
  4 เขื่อนเจ้าพระยา/ป่าสัก/พระรามหกคุมน้ำ · 5 ผ่าน กทม. ในคันกั้นน้ำ · 6 ทำไมสายไหมไม่ท่วมเพิ่มจากน้ำเหนือ
  7 สิ่งที่ยังต้องระวัง
ตัวเลขจากข้อมูลในโปรเจกต์ (ฝน เขื่อน ธงภัย สถิติ 3 ปี) + ตัวเลขประกาศทางการ (OFFICIAL พร้อมแหล่งอ้างอิง)
ข้อความสำคัญ: น้ำเหนือกระทบ "ริมแม่น้ำนอกคันกั้นน้ำ" จริง แต่แทบไม่เพิ่มน้ำในสายไหม/พื้นที่ในคัน"""
import json, os, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: json.load(open(os.path.join(BASE, *p)))
RIV = J("data", "geo", "north_rivers.json")
V = J("data", "dams_verified.json")
FL = J("data", "river_flags.json")["flags"]
FH = J("data", "flag_history.json")
RP = J("data", "impact", "rain_provinces.json")
ST = J("data", "impact", "stations.json")
RAIN = J("data", "impact", "rain.json")["obs"]["saimai"]
IMP = J("data", "impact_forecast.json")
ROUTES = J("data", "geo", "routes.json")

# ตัวเลขประกาศทางการ (ไม่มีใน API ที่เราดึง) · อัปเดตมือเมื่อมีประกาศใหม่
OFFICIAL = {
    "as_of": "28-29 ก.ย. 2569",
    "c2_before": 1400, "c2_now": 1904, "c2_expect": "2,000-2,200",
    "cpy_dam": "2,000-2,200",
    "pasak_plan": "115 → 230 → 400", "pasak_river_rise": "3.5-4.0",
    "rama6_in": 700, "rama6_canal": 50, "rama6_river": 650,
    "bkk_flow": 2000, "bkk_wall": 3.0, "bkk_spare": 1.8, "bkk_outside_rise": "0.6-1.5",
    "sources": [
        ["Nation: RID warns 8 provinces (C.2 1,904 m³/s)", "https://www.nationthailand.com/news/general/40071623"],
        ["Nation: Chao Phraya Dam 2,000 m³/s", "https://www.nationthailand.com/news/general/40071594"],
        ["Thai PBS: แผนระบายป่าสัก", "https://www.thaipbs.or.th/news/content/558792"],
        ["Khaosod English: พระรามหก 700 / 50 m³/s", "https://www.khaosodenglish.com/news/2026/09/28/rama-vi-dam-raises-red-flag-as-pasak-river-levels-rise/"],
        ["กรุงเทพธุรกิจ: น้ำเหนือยังไม่ล้นคัน (2,000 m³/s คัน ~3 ม.)", "https://www.bangkokbiznews.com/news/news-update/1254195"],
        ["กรุงเทพธุรกิจ: รัฐบาล รับได้อีก 1.8 ม.", "https://www.bangkokbiznews.com/politics/1254188"],
        ["Nation: กทม. เตือนริมเจ้าพระยา +0.61-1.50 ม.", "https://www.nationthailand.com/news/general/40071311"],
        ["กรุงเทพธุรกิจ: ปภ. เตือนสายไหม คลองหกวาล้นคัน", "https://www.bangkokbiznews.com/news/news-update/1254210"],
    ],
}


def D(d, k):
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=k)).isoformat()


today = RP["today"]
# ---------- ฝนรายจังหวัด ----------
prov = []
for p in RP["provinces"]:
    dly = p["daily"]
    prov.append({"name": p["name"], "river": p["river"], "lat": p["lat"], "lon": p["lon"],
                 "ev": round(sum(v for d, v in dly.items() if "2026-09-25" <= d <= "2026-09-28")),
                 "f7": round(sum(v for d, v in dly.items() if today < d <= D(today, 7)))})

# ---------- เขื่อน ----------
dams = {d["name"]: d for d in V["dams"]}
pick = ["ภูมิพล", "สิริกิติ์", "กิ่วลม", "แควน้อยบำรุงแดน", "ป่าสักชลสิทธิ์", "ทับเสลา"]
dam_pts = [{"name": n, "lat": dams[n]["lat"], "lon": dams[n]["lon"], "pct": dams[n]["pct"], "out": dams[n]["outflow"],
            "inf": dams[n]["inflow"], "room": round(dams[n]["normal"] - dams[n]["volume"]) if dams[n]["volume"] else None}
           for n in pick if n in dams]

# ---------- ธงภัยสำคัญ (สูงสุด 3 วันล่าสุดจากประวัติ) ----------
def flag(code):
    f = next((x for x in FL if x["code"] == code), None)
    if not f:
        return None
    h = FH.get(str(f["id"]), {})
    last3 = [h[d] for d in sorted(h)[-3:]]
    return {"code": code, "name": f["name"], "pro": f["pro"], "lat": f["lat"], "lon": f["lon"],
            "pct": round(f["pct"]) if f["pct"] is not None else None, "max3": max(last3) if last3 else None, "sev": f["sev"]}


KEY_FLAGS = ["PIN002", "P.7A", "PIN004", "P.17", "VLGE13", "Y.5", "N.7A", "C.2", "C.13", "CPY008", "C.35", "PAS008", "S.26",
             "CPY014", "C.12", "BKK001", "BKK015"]
flags = [f for f in (flag(c) for c in KEY_FLAGS) if f]

# ---------- สถิติ 3 ปี: C.2 ขึ้นแรงแล้วสายไหมเป็นยังไง ----------
C2 = {d: v[0] for d, v in ST["2795"]["daily"].items()}
SM = {d: v[0] for d, v in ST["11"]["daily"].items()}
ev = [d for d in C2 if D(d, -7) in C2 and C2[d] - C2[D(d, -7)] > 1.0 and d in SM and D(d, 5) in SM]
dry = [SM[D(d, 5)] - SM[d] for d in ev if sum(RAIN.get(D(d, k), 0) for k in range(1, 6)) < 20]
wet = [(d, SM[D(d, 5)] - SM[d], sum(RAIN.get(D(d, k), 0) for k in range(-2, 6))) for d in ev
       if sum(RAIN.get(D(d, k), 0) for k in range(1, 6)) >= 100]
stat = {"n": len(ev), "n_dry": len(dry), "dry_mean_cm": round(sum(dry) / len(dry) * 100) if dry else None,
        "dry_max_cm": round(max(dry) * 100) if dry else None}

# ---------- เส้นคลองระพีพัฒน์ → สายไหม (OSM route ป่าสัก #2) ----------
rapipat = ROUTES.get("ป่าสักชลสิทธิ์", [None, None])[1]
rapipat = [p for p in rapipat["line"]][::3] if rapipat else []

S11 = IMP["targets"]["11"]
DATA = {"riv": RIV, "prov": prov, "dams": dam_pts, "flags": flags, "stat": stat, "off": OFFICIAL, "rapipat": rapipat,
        "today": today, "sm": {"level": S11["level0"], "flood": S11["flood_level"], "cap": IMP["drop_cap_now"]["11"]["cm_per_day"],
                               "rain_ev": round(sum(RAIN.get(d, 0) for d in RAIN if "2026-09-25" <= d <= "2026-09-28")),
                               "min_gap": round(min(S11["flood_level"] - x["level"] for x in S11["h"]) * 100),
                               "rain2x_over": sum(x["level_rain2x"] >= S11["flood_level"] for x in S11["h"])},
        "home": [13.9175, 100.6512]}

HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>น้ำเหนือไปไหน</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1c1c1a;--sub:#5f5f5a;--mut:#8a8a84;--line:#e4e3de;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;
--t1:#184f95;--t2:#3987e5;--t3:#86b6ef;--riv:#c7d5e6;--water:#2a78d6;--land:#efeee9;--link:#256abf}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--card:#1a1a19;--ink:#ededea;--sub:#b5b5ae;--mut:#85857f;
--line:#2e2e2b;--t1:#9ec5f4;--t2:#5598e7;--t3:#256abf;--riv:#2c3a4d;--water:#6da7ec;--land:#1f1f1d;--link:#86b6ef}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--ink:#ededea;--sub:#b5b5ae;--mut:#85857f;--line:#2e2e2b;--t1:#9ec5f4;--t2:#5598e7;
--t3:#256abf;--riv:#2c3a4d;--water:#6da7ec;--land:#1f1f1d;--link:#86b6ef}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Sarabun","Noto Sans Thai",sans-serif;font-size:15px}
a{color:var(--link)}
.wrap{max-width:1180px;margin:0 auto;padding:14px 16px 40px}
h1{font-size:1.35rem;margin:0}
.mut{color:var(--mut);font-size:.8rem}.sub{color:var(--sub)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:14px;margin-top:12px;align-items:start}
@media (max-width:860px){.grid{grid-template-columns:1fr}}
#map{position:relative}
#map svg{width:100%;height:auto;display:block;border-radius:10px;background:var(--land)}
.riv{fill:none;stroke:var(--riv);stroke-linecap:round;stroke-linejoin:round;transition:stroke .6s,opacity .6s;vector-effect:non-scaling-stroke}
.riv.on{stroke:var(--water);stroke-dasharray:6 9;animation:flow 1.2s linear infinite}
.riv.dim{opacity:.35}
@keyframes flow{to{stroke-dashoffset:-15}}
@media (prefers-reduced-motion:reduce){.riv.on{animation:none;stroke-dasharray:none}}
.lbl{font-size:11px;fill:var(--ink);paint-order:stroke;stroke:var(--land);stroke-width:3px;stroke-linejoin:round}
.lblb{font-weight:700;font-size:12.5px}
.layer{transition:opacity .6s}
.hide{opacity:0;pointer-events:none}
#scene h2{font-size:1.15rem;margin:.1em 0 .4em}
#scene .big{font-size:1.5rem;font-weight:700;font-variant-numeric:tabular-nums}
#scene p{line-height:1.65;margin:.5em 0}
.nums{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}
.num{border:1px solid var(--line);border-radius:10px;padding:8px 10px}.num .l{font-size:.78rem;color:var(--sub)}
.ctrl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px}
button{font:inherit;font-size:.85rem;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:5px 12px;cursor:pointer}
button:hover{border-color:var(--link)}button.on{background:var(--t1);color:#fff;border-color:var(--t1)}
.dots{display:flex;gap:6px;flex-wrap:wrap}
.dot{width:30px;height:6px;border-radius:3px;background:var(--line);cursor:pointer;position:relative;overflow:hidden}
.dot.done{background:var(--t2)}.dot i{position:absolute;left:0;top:0;bottom:0;background:var(--t2)}
.verdict{border-left:4px solid var(--warn);padding:6px 12px;background:var(--bg);border-radius:0 8px 8px 0;margin:10px 0}
.xs svg{width:100%;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:.84rem}
td,th{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right}td:first-child,th:first-child{text-align:left}
</style>
</head>
<body>
<div class="wrap">
<h1>น้ำเหนือไปไหน · ทำไมไม่ทำให้สายไหมท่วมเพิ่ม · ใครได้รับผลจริง</h1>
<div class="mut" id="stamp"></div>
<div class="verdict" id="verdict"></div>
<div class="grid">
  <div class="card" id="map"></div>
  <div>
    <div class="card" id="scene"></div>
    <div class="ctrl">
      <button id="play" class="on">⏸ หยุด</button><button id="prev">◀ ก่อนหน้า</button><button id="next">ถัดไป ▶</button>
      <div class="dots" id="dots"></div>
    </div>
  </div>
</div>
<div class="card" style="margin-top:14px">
  <b>ตัวเลขทางการที่ใช้ (ประกาศ ณ <span id="asof"></span>)</b>
  <div class="mut" id="srcs" style="line-height:1.8;margin-top:4px"></div>
  <div class="mut" style="margin-top:6px">ข้อมูลในโปรเจกต์: เส้นแม่น้ำ HydroRIVERS · ฝน Open-Meteo · เขื่อน RID · ระดับน้ำ thaiwater (สสน.) ·
  สถิติ 3 ปีจากสถานี C.2 และสายไหม · <a href="saimai-forecast.html">พยากรณ์สายไหม 14 วัน</a> · <a href="dashboard.html">เขื่อนทั่วประเทศ</a></div>
</div>
</div>
<script>
const D = __DATA__, O = D.off;
const $ = id => document.getElementById(id);
const f0 = v => v == null ? '–' : Math.round(v).toLocaleString('th-TH');
const THM = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const thd = d => { const [y, m, dd] = d.split('-').map(Number); return dd + ' ' + THM[m - 1] + ' ' + (y + 543) };
$('stamp').textContent = 'ข้อมูล ณ ' + thd(D.today) + ' · แผนที่ลำน้ำจริงลุ่มเจ้าพระยา ~144,000 km² · เส้นเคลื่อนไหว = ทิศที่น้ำไหล';
$('asof').textContent = O.as_of;
$('srcs').innerHTML = O.sources.map(s => '<a href="' + s[1] + '">' + s[0] + '</a>').join(' · ');
$('verdict').innerHTML = '<b>สรุป:</b> น้ำเหนือ<b>ไม่ได้ไม่มีผลต่อกรุงเทพฯ</b> — ริมเจ้าพระยา<b>นอกคันกั้นน้ำ</b>ได้รับผลจริง (ทางการเตือน +' + O.bkk_outside_rise +
  ' ม.) · แต่<b>สายไหมและพื้นที่ในคันกั้นน้ำ</b>แทบไม่ได้รับน้ำเหนือเพิ่ม เพราะคันกั้นน้ำยังรับได้ และน้ำเกือบทั้งหมดอยู่ในแม่น้ำ ไม่ถูกผันเข้าคลองฝั่งตะวันออก · ' +
  'สายไหมท่วมตอนนี้เพราะ<b>ฝนในพื้นที่ ' + D.sm.rain_ev + ' มม.</b> (25-28 ก.ย.)';

// ---------- แผนที่ ----------
const LON0 = 97.9, LON1 = 101.75, LAT0 = 13.45, LAT1 = 19.95, K = Math.cos(16.5 * Math.PI / 180), SC = 130;
const X = lon => (lon - LON0) * K * SC, Y = lat => (LAT1 - lat) * SC;
const FULL = [0, 0, (LON1 - LON0) * K * SC, (LAT1 - LAT0) * SC];
const pth = g => 'M' + g.map(p => X(p[1]).toFixed(1) + ' ' + Y(p[0]).toFixed(1)).join('L');
let s = '<svg id="svg" viewBox="' + FULL.join(' ') + '" role="img" aria-label="แผนที่ลำน้ำลุ่มเจ้าพระยา">';
const NAMES = {ping: 'ปิง', wang: 'วัง', yom: 'ยม', nan: 'น่าน', pasak: 'ป่าสัก', cpy: 'เจ้าพระยา'};
Object.entries(D.riv).forEach(([g, chains]) => {
  s += '<g id="r_' + g + '">';
  chains.forEach(c => { const w = Math.max(.8, Math.min(7, Math.sqrt(c.up) / 38));
    s += '<path class="riv" d="' + pth(c.g) + '" stroke-width="' + w.toFixed(2) + '"/>' });
  s += '</g>';
});
// คลองระพีพัฒน์ → สายไหม (เส้นบางตามสัดส่วนน้ำที่ผัน)
s += '<path id="rapipat" class="riv" d="' + pth(D.rapipat) + '" stroke-width="1.6"/>';
// ชื่อแม่น้ำ
[['ปิง', 18.3, 98.75], ['วัง', 18.2, 99.62], ['ยม', 17.9, 100.05], ['น่าน', 18.1, 100.72], ['ป่าสัก', 16.1, 101.2], ['เจ้าพระยา', 14.9, 100.12]]
  .forEach(n => s += '<text class="lbl" x="' + X(n[2]) + '" y="' + Y(n[1]) + '" font-style="italic" fill="var(--t1)">' + n[0] + '</text>');
// ชั้น: ฝน / เขื่อน / ธง / จุดสำคัญ / กทม.
s += '<g id="L_rain" class="layer hide"></g><g id="L_dams" class="layer hide"></g><g id="L_flagsN" class="layer hide"></g><g id="L_flagsS" class="layer hide"></g>' +
  '<g id="L_pts" class="layer"></g><g id="L_bkk" class="layer hide"></g><g id="L_sm" class="layer hide"></g></svg>';
$('map').innerHTML = s + '<div class="xs" id="xs" style="display:none;margin-top:8px"></div>';
const svg = $('svg');
const put = (id, html) => svg.querySelector('#' + id).innerHTML = html;
// ไอคอน/ตัวหนังสือทุกตัวอยู่ใน <g class="mk"> ที่พิกัดจริง แล้วสเกล 1/zoom ทุกเฟรม → ขนาดบนจอคงที่ทุกระดับซูม
const mk = (lat, lon, inner) => '<g class="mk" data-x="' + X(lon).toFixed(1) + '" data-y="' + Y(lat).toFixed(1) + '">' + inner + '</g>';
put('L_rain', D.prov.map(p => { const r = 4 + Math.sqrt(p.ev) * 1.6;
  return mk(p.lat, p.lon, '<circle r="' + r + '" fill="var(--t2)" opacity=".28" stroke="var(--t1)" stroke-width="1"/>' +
    '<text class="lbl" x="' + (r + 3) + '" y="4">' + p.name + ' <tspan font-weight="700">' + p.ev + '</tspan></text>') }).join(''));
put('L_dams', D.dams.map(d => { const h = 26, fill = Math.min(1.2, d.pct / 100) * h / 1.2;
  const col = d.pct > 100 ? 'var(--crit)' : d.pct >= 80 ? 'var(--warn)' : 'var(--good)';
  return mk(d.lat, d.lon, '<rect x="-7" y="' + (-h) + '" width="14" height="' + h + '" rx="3" fill="var(--card)" stroke="var(--ink)"/>' +
    '<rect x="-5" y="' + (-2 - fill) + '" width="10" height="' + fill + '" rx="2" fill="' + col + '"/>' +
    '<text class="lbl lblb" x="10" y="-14">' + d.name + ' ' + f0(d.pct) + '%</text>' +
    '<text class="lbl" x="10" y="-1">ระบาย ' + (+d.out).toFixed(1) + ' ล้าน/วัน</text>') }).join(''));
const FC = ['var(--good)', 'var(--warn)', 'var(--crit)'];
const flagG = codes => D.flags.filter(f => codes.includes(f.code)).map(f => mk(f.lat, f.lon,
  '<line x1="0" y1="0" x2="0" y2="-16" stroke="var(--ink)" stroke-width="1.5"/>' +
  '<path d="M0 -16L11 -12.5L0 -9Z" fill="' + FC[f.sev] + '" stroke="var(--ink)" stroke-width=".8"/>' +
  '<text class="lbl" x="13" y="-9">' + f.name.slice(0, 14) + ' ' + f0(f.max3) + '%</text>')).join('');
put('L_flagsN', flagG(['PIN002', 'PIN004', 'VLGE13', 'N.7A', 'C.2']));      // ฉาก 3: น้ำเหนือ
put('L_flagsS', flagG(['C.13', 'CPY008', 'C.35', 'PAS008']));              // ฉาก 4: เจ้าพระยาตอนล่าง/ป่าสัก
// จุดสำคัญ
const PTS = [['C.2 นครสวรรค์', 15.67, 100.12], ['เขื่อนเจ้าพระยา', 15.16, 100.18], ['พระรามหก', 14.56, 100.72], ['อยุธยา', 14.35, 100.57], ['กรุงเทพฯ', 13.75, 100.5]];
put('L_pts', PTS.map(p => mk(p[1], p[2], '<circle r="3.5" fill="var(--ink)"/><text class="lbl lblb" x="-6" y="15" text-anchor="end">' + p[0] + '</text>')).join(''));
// กทม.: แนวเจ้าพระยาในเมือง (แถบแดงจาง = ริมน้ำนอกคัน)
const cpyBkk = D.riv.cpy.flatMap(c => c.g).filter(p => p[0] < 14.05 && p[0] > 13.55).sort((a, b) => b[0] - a[0]);
put('L_bkk', '<path d="' + pth(cpyBkk) + '" fill="none" stroke="var(--crit)" stroke-width="14" opacity=".2" vector-effect="non-scaling-stroke"/>' +
  mk(13.86, 100.47, '<text class="lbl lblb" x="-8" y="0" text-anchor="end" fill="var(--crit)">ริมเจ้าพระยานอกคัน</text>' +
    '<text class="lbl" x="-8" y="14" text-anchor="end">ทางการเตือน +' + O.bkk_outside_rise + ' ม.</text>'));
put('L_sm', mk(D.home[0], D.home[1], '<circle r="16" fill="var(--warn)" opacity=".3"/>' +
  '<path d="M-6 4l6 -6 6 6v6h-12z" fill="var(--card)" stroke="var(--ink)"/>' +
  '<text class="lbl lblb" x="14" y="-4">สายไหม (บ้าน)</text>' +
  '<text class="lbl" x="14" y="10">ฝน 25-28 ก.ย. ' + D.sm.rain_ev + ' มม.</text>'));
const MKS = [...svg.querySelectorAll('.mk')];
function scaleMarks(z) { MKS.forEach(g => g.setAttribute('transform', 'translate(' + g.dataset.x + ',' + g.dataset.y + ') scale(' + (1 / z).toFixed(4) + ')')) }
// ชื่อแม่น้ำก็สเกลตาม
const RLBL = [...svg.querySelectorAll('text[font-style="italic"]')];

// ---------- ภาพตัดขวางแม่น้ำ กทม. (ฉาก 5) ----------
function crossSection() {
  const W = 520, H = 190, base = 165, m = 38;   // 1 ม. = 38 px จากท้องน้ำเทียม
  const wall = O.bkk_wall, now = O.bkk_wall - O.bkk_spare, lo = parseFloat(O.bkk_outside_rise.split('-')[0]), hi = parseFloat(O.bkk_outside_rise.split('-')[1]);
  const y = v => base - v * m;
  let g = '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="var(--land)" rx="8"/>';
  g += '<path d="M120 ' + base + ' Q260 ' + (base + 40) + ' 400 ' + base + ' Z" fill="var(--water)" opacity=".2"/>';
  g += '<rect x="120" y="' + y(now) + '" width="280" height="' + (base - y(now)) + '" fill="var(--water)" opacity=".75"/>';
  g += '<rect x="120" y="' + y(now + hi) + '" width="280" height="' + (y(now) - y(now + hi)) + '" fill="var(--water)" opacity=".25"/>';
  // คันกั้นน้ำ
  [[108, 120], [400, 412]].forEach(([a, b]) => g += '<rect x="' + a + '" y="' + y(wall) + '" width="' + (b - a) + '" height="' + (base - y(wall)) + '" fill="var(--sub)"/>');
  // พื้นที่นอกคัน (ชุมชนริมน้ำระหว่างคันกับแม่น้ำ) และในเมือง
  g += '<rect x="0" y="' + y(1.2) + '" width="108" height="' + (base - y(1.2)) + '" fill="var(--card)" stroke="var(--line)"/>';
  g += '<rect x="412" y="' + y(1.2) + '" width="108" height="' + (base - y(1.2)) + '" fill="var(--card)" stroke="var(--line)"/>';
  g += '<text x="54" y="' + (y(1.2) - 6) + '" text-anchor="middle" font-size="11" fill="var(--ink)">เมือง (ในคัน)</text>';
  g += '<text x="466" y="' + (y(1.2) - 6) + '" text-anchor="middle" font-size="11" fill="var(--ink)">เมือง (ในคัน)</text>';
  g += '<rect x="300" y="' + y(now + .2) + '" width="60" height="16" fill="var(--crit)" opacity=".85"/><text x="330" y="' + (y(now + .2) + 12) + '" text-anchor="middle" font-size="10" fill="#fff">บ้านนอกคัน</text>';
  g += '<line x1="100" x2="420" y1="' + y(wall) + '" y2="' + y(wall) + '" stroke="var(--crit)" stroke-dasharray="4 3"/>';
  g += '<text x="260" y="' + (y(wall) - 5) + '" text-anchor="middle" font-size="11" fill="var(--crit)">สันคัน ~' + wall.toFixed(1) + ' ม.</text>';
  g += '<text x="260" y="' + (y(now) + 16) + '" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">น้ำตอนนี้ ~' + O.bkk_flow.toLocaleString() + ' m³/s</text>';
  g += '<text x="130" y="' + (y(now + hi) + 13) + '" font-size="11" fill="var(--ink)">คาดเพิ่ม +' + O.bkk_outside_rise + ' ม. · ยังต่ำกว่าสันคัน</text>';
  g += '<text x="20" y="' + (H - 6) + '" font-size="10" fill="var(--mut)">ภาพตัดขวางแบบย่อ ไม่ตามมาตราส่วนจริง · ตัวเลขจากประกาศทางการ</text>';
  return '<svg viewBox="0 0 ' + W + ' ' + H + '">' + g + '</svg>';
}

// ---------- ฉาก ----------
const f = c => D.flags.find(x => x.code === c) || {};
const dam = n => D.dams.find(x => x.name === n) || {};
const pv = n => D.prov.find(x => x.name === n) || {};
const BKK_BOX = [X(100.25), Y(14.75), X(100.95) - X(100.25), Y(13.55) - Y(14.75)];
const SM_BOX = [X(100.4), Y(14.3), X(100.95) - X(100.4), Y(13.75) - Y(14.3)];
const SCENES = [
  {t: '1 · ต้นเหตุ: ฝนหนัก 25-28 ก.ย.', box: FULL, on: [], layers: ['L_rain', 'L_sm'],
   h: () => '<p>ฝนก้อนใหญ่ตก<b>ภาคเหนือตอนล่างถึงกรุงเทพฯ</b> ไม่ใช่ภาคเหนือตอนบน (วงกลม = ฝนรวม 4 วัน มม.)</p>' +
     '<div class="nums">' + [['ตาก/กำแพงเพชร', pv('ตาก').ev + '/' + pv('กำแพงเพชร').ev], ['นครสวรรค์/ชัยนาท', pv('นครสวรรค์').ev + '/' + pv('ชัยนาท').ev],
       ['อยุธยา', pv('อยุธยา').ev], ['สายไหม', pv('สายไหม').ev], ['เชียงใหม่/น่าน (บน)', pv('เชียงใหม่').ev + '/' + pv('น่าน').ev],
       ['7 วันข้างหน้า สายไหม', pv('สายไหม').f7]].map(n => '<div class="num"><div class="big">' + n[1] + '</div><div class="l">' + n[0] + ' (มม.)</div></div>').join('') + '</div>' +
     '<p class="sub">ฝนก้อนเดียวกันนี้ทำ 2 อย่าง: เติมน้ำเข้าแม่น้ำ (เดินทางมาเป็น "น้ำเหนือ" ในอีกหลายวัน) และตกใส่สายไหมโดยตรงจนคลองล้นทันที</p>'},
  {t: '2 · เขื่อนใหญ่ภาคเหนือรับน้ำไว้ ไม่ได้ล้น', box: FULL, on: [], dim: ['ping', 'wang', 'yom', 'nan'], layers: ['L_dams'],
   h: () => '<p>ภูมิพล (ปิง) และสิริกิติ์ (น่าน) คือถังใหญ่ของลุ่ม ตอนนี้<b>ยังรับน้ำได้อีกมาก</b>และปล่อยน้ำน้อยมาก</p>' +
     '<div class="nums">' + ['ภูมิพล', 'สิริกิติ์'].map(n => '<div class="num"><div class="big">' + f0(dam(n).pct) + '%</div><div class="l">' + n +
       ' · รับได้อีก ~' + f0(dam(n).room) + ' ล้าน ลบ.ม. · ระบาย ' + (+dam(n).out).toFixed(1) + ' ล้าน/วัน</div></div>').join('') + '</div>' +
     '<p class="sub">น้ำฝนที่ตกเหนือเขื่อนจึงถูกเก็บไว้ ไม่ไหลลงมาเพิ่ม · เขื่อนที่เกิน 100% ในลุ่มเจ้าพระยามีแค่<b>ป่าสัก</b> (ฉาก 4)</p>'},
  {t: '3 · น้ำเหนือก้อนนี้มาจากไหน (ที่มาของ "+50%")', box: FULL, on: ['ping', 'yom', 'cpy'], dim: ['wang', 'nan', 'pasak'], layers: ['L_flagsN'],
   h: () => '<p>น้ำที่กำลังมาคือฝนที่ตก<b>ใต้เขื่อน</b> ไหลลง<b>ปิงตอนล่าง (ตาก-กำแพงเพชร)</b> และ<b>ยมตอนล่าง</b> (ยมไม่มีเขื่อนใหญ่กั้น) มาบรรจบที่นครสวรรค์</p>' +
     '<div class="nums"><div class="num"><div class="big">' + f0(f('PIN002').max3) + '%</div><div class="l">เมืองตาก (ปิง) % ตลิ่ง สูงสุด 3 วัน</div></div>' +
     '<div class="num"><div class="big">' + f0(f('VLGE13').max3) + '%</div><div class="l">ยมตอนล่าง พิษณุโลก</div></div>' +
     '<div class="num"><div class="big">' + O.c2_before.toLocaleString() + ' → ' + O.c2_expect + '</div><div class="l">C.2 นครสวรรค์ m³/s = <b>+43-57%</b></div></div>' +
     '<div class="num"><div class="big">' + f0(f('C.2').max3) + '%</div><div class="l">C.2 % ตลิ่ง (ยังขึ้น)</div></div></div>' +
     '<p class="sub">"+50%" คือ<b>อัตราการไหลของแม่น้ำที่นครสวรรค์</b> ไม่ใช่ระดับน้ำที่สายไหม · วังและน่านกำลังลด</p>'},
  {t: '4 · เขื่อนเจ้าพระยา ป่าสัก และพระรามหก คุมทางไปของน้ำ', box: FULL, on: ['cpy', 'pasak'], dim: ['ping', 'wang', 'yom', 'nan'], layers: ['L_flagsS'], rap: 'thin',
   h: () => '<p>น้ำจากนครสวรรค์ถึงเขื่อนเจ้าพระยาใน ~1 วัน ถึงอยุธยา ~2 วัน (สถิติ 3 ปี) · ป่าสักเต็ม จึงระบายเพิ่ม</p>' +
     '<div class="nums"><div class="num"><div class="big">' + O.cpy_dam + '</div><div class="l">เขื่อนเจ้าพระยาระบาย m³/s</div></div>' +
     '<div class="num"><div class="big">' + O.pasak_plan + '</div><div class="l">ป่าสักระบาย m³/s (30 ก.ย.-2 ต.ค.) แม่น้ำป่าสัก +' + O.pasak_river_rise + ' ม.</div></div>' +
     '<div class="num"><div class="big">' + O.rama6_river + ' : ' + O.rama6_canal + '</div><div class="l">พระรามหก: ลงแม่น้ำ : ผันเข้าคลองระพีพัฒน์ (m³/s)</div></div>' +
     '<div class="num"><div class="big">' + Math.round(O.rama6_canal / O.rama6_in * 100) + '%</div><div class="l">สัดส่วนที่เข้าคลองมาทางสายไหม</div></div></div>' +
     '<p class="sub">เส้นบางสีฟ้าทางขวา = คลองระพีพัฒน์ → คลองรังสิต → คลองสอง → สายไหม · น้ำ<b>เกือบทั้งหมดอยู่ในแม่น้ำ</b> ริมแม่น้ำป่าสัก (ท่าเรือ นครหลวง อยุธยา) จึงเป็นพื้นที่ที่ถูกเตือน</p>'},
  {t: '5 · ผ่านกรุงเทพฯ ในคันกั้นน้ำ', box: BKK_BOX, on: ['cpy'], dim: ['pasak'], layers: ['L_bkk', 'L_sm'], xs: true,
   h: () => '<p>ถึงช่วงกรุงเทพฯ ราว <b>3-6 ต.ค.</b> ซึ่งตรงกับ<b>ช่วงน้ำตาย</b> (น้ำทะเลหนุนต่ำ) ช่วยได้ · น้ำเกิดอีกรอบ 10-13 ต.ค.</p>' +
     '<div class="nums"><div class="num"><div class="big">~' + O.bkk_flow.toLocaleString() + '</div><div class="l">เจ้าพระยาผ่าน กทม. m³/s</div></div>' +
     '<div class="num"><div class="big">' + O.bkk_spare + ' ม.</div><div class="l">คันกั้นน้ำ (~' + O.bkk_wall + ' ม.) ยังรับได้อีก</div></div></div>' +
     '<p><b>ใครได้รับผล:</b> ชุมชน<b>ริมแม่น้ำนอกคันกั้นน้ำ</b> (ภาพล่าง สีแดง) ทางการเตือน +' + O.bkk_outside_rise + ' ม. · ' +
     '<b>ในเมืองหลังคัน</b> น้ำเหนือไม่ข้ามมา ตราบที่คันยังรับได้</p>'},
  {t: '6 · ทำไมสายไหมไม่ท่วมเพิ่มจากน้ำเหนือ', box: SM_BOX, on: [], dim: ['cpy'], layers: ['L_sm'], rap: 'on',
   h: () => '<p>สายไหมอยู่<b>หลังคันกั้นน้ำ</b> รับน้ำจากคลอง ไม่ได้รับจากแม่น้ำตรง · ทางเดียวที่น้ำเหนือเข้ามาได้คือคลองระพีพัฒน์ ซึ่งรับแค่ ~' +
     Math.round(O.rama6_canal / O.rama6_in * 100) + '% ของน้ำป่าสัก</p>' +
     '<div class="nums"><div class="num"><div class="big">' + D.stat.n + ' วัน</div><div class="l">ใน 3 ปี ที่ C.2 ขึ้นเกิน 1 ม. ใน 7 วัน</div></div>' +
     '<div class="num"><div class="big">' + (D.stat.dry_mean_cm > 0 ? '+' : '') + D.stat.dry_mean_cm + ' ซม.</div><div class="l">สายไหมเฉลี่ย 5 วันถัดมา (ช่วงไม่มีฝนในพื้นที่ ' + D.stat.n_dry + ' วัน)</div></div></div>' +
     '<p>ครั้งเดียวที่สายไหมขึ้นแรงคือรอบนี้ ซึ่ง<b>ตรงกับฝนในพื้นที่ ' + D.sm.rain_ev + ' มม.</b> · ข้อมูลจึงบอกว่า<b>ตัวคุมสายไหมคือฝน ไม่ใช่น้ำเหนือ</b></p>' +
     '<p class="sub">ผลทางอ้อมที่มีจริง: ตอนแม่น้ำสูง คลองระบายลงแม่น้ำได้ช้า น้ำที่ท่วมอยู่จึงลดช้า (ตอนนี้ ~' + D.sm.cap + ' ซม./วัน)</p>'},
  {t: '7 · สิ่งที่ยังต้องระวัง', box: SM_BOX, on: [], layers: ['L_sm', 'L_rain'],
   h: () => '<p>สายไหม<b>ท่วมอยู่แล้ว</b> (ปภ. เตือนคลองหกวาล้นคัน) ระดับวันนี้ ' + D.sm.level.toFixed(2) + ' ม. = ระดับที่ท่วม · น้ำเหนือไม่ทำให้สูงขึ้น แต่:</p>' +
     '<p>• พยากรณ์ 14 วัน ค้างอยู่ต่ำกว่าระดับท่วมแค่ ' + D.sm.min_gap + ' ซม.ขึ้นไป — ลดช้า<br>• ฝนพยากรณ์ 7 วัน ' + pv('สายไหม').f7 + ' มม. (หนักสุด ~6 ต.ค.) ถ้าตกมากกว่าพยากรณ์ 2 เท่า เกินระดับท่วม ' +
     D.sm.rain2x_over + ' จาก 14 วัน<br>• น้ำเกิด 10-13 ต.ค. คลองระบายช้าลงอีก</p>' +
     '<div class="verdict"><b>ควรยกของขึ้นที่สูงตามคำเตือน</b> — เหตุผลไม่ใช่น้ำเหนือ แต่คือน้ำที่ท่วมอยู่ลดช้าและฝนที่อาจมาเพิ่ม</div>' +
     '<p><a href="saimai-forecast.html">ดูพยากรณ์ระดับน้ำสายไหม 14 วัน →</a></p>'},
];

// ---------- เล่นฉาก ----------
let cur = 0, playing = true, t0 = performance.now(), vb = FULL.slice(), vbFrom = FULL.slice(), vbTo = FULL.slice(), vbT = 1;
const DUR = 9000;
$('dots').innerHTML = SCENES.map((_, i) => '<div class="dot" data-i="' + i + '"><i></i></div>').join('');
$('dots').querySelectorAll('.dot').forEach(d => d.onclick = () => go(+d.dataset.i, true));
function go(i, user) {
  cur = (i + SCENES.length) % SCENES.length; t0 = performance.now();
  if (user) { playing = false; $('play').textContent = '▶ เล่น'; $('play').classList.remove('on') }
  const S = SCENES[cur];
  $('scene').innerHTML = '<h2>' + S.t + '</h2>' + S.h();
  Object.keys(D.riv).forEach(g => svg.querySelectorAll('#r_' + g + ' path').forEach(p => {
    p.classList.toggle('on', S.on.includes(g)); p.classList.toggle('dim', (S.dim || []).includes(g)) }));
  const rp = svg.querySelector('#rapipat');
  rp.classList.toggle('on', S.rap === 'on' || S.rap === 'thin'); rp.style.opacity = S.rap ? 1 : .25;
  ['L_rain', 'L_dams', 'L_flagsN', 'L_flagsS', 'L_bkk', 'L_sm'].forEach(l => svg.querySelector('#' + l).classList.toggle('hide', !(S.layers || []).includes(l)));
  $('xs').style.display = S.xs ? 'block' : 'none'; if (S.xs) $('xs').innerHTML = crossSection();
  vbFrom = vb.slice(); vbTo = S.box; vbT = 0;
  $('dots').querySelectorAll('.dot').forEach((d, k) => { d.classList.toggle('done', k < cur); d.querySelector('i').style.width = '0' });
}
function frame(now) {
  if (vbT < 1) { vbT = Math.min(1, vbT + 1 / 40); const e = vbT < .5 ? 2 * vbT * vbT : 1 - Math.pow(-2 * vbT + 2, 2) / 2;
    vb = vbFrom.map((a, k) => a + (vbTo[k] - a) * e); svg.setAttribute('viewBox', vb.join(' '));
    const z = FULL[2] / vb[2]; scaleMarks(z);
    RLBL.forEach(t => t.style.fontSize = (11 / z).toFixed(2) + 'px') }
  const p = Math.min(1, (now - t0) / DUR);
  const dot = $('dots').querySelectorAll('.dot')[cur]; if (dot) dot.querySelector('i').style.width = (playing ? p * 100 : 100) + '%';
  if (playing && p >= 1) go(cur + 1);
  requestAnimationFrame(frame);
}
$('play').onclick = () => { playing = !playing; t0 = performance.now(); $('play').textContent = playing ? '⏸ หยุด' : '▶ เล่น'; $('play').classList.toggle('on', playing) };
$('prev').onclick = () => go(cur - 1, true); $('next').onclick = () => go(cur + 1, true);
if (matchMedia('(prefers-reduced-motion: reduce)').matches) { playing = false; $('play').textContent = '▶ เล่น'; $('play').classList.remove('on') }
go(0); requestAnimationFrame(frame);
</script>
</body></html>
"""

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
out = os.path.join(BASE, "north-water.html")
open(out, "w").write(html)
print("OK", out, f"size={len(html.encode()) / 1e3:.0f} KB · stat={stat}")
