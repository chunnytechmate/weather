#!/usr/bin/env python3
"""ประกอบ dashboard.html: เขื่อนใหญ่ทั่วประเทศ (หน้าหลัก)

   - ค่าทุกเขื่อนมาจาก data/dams_verified.json (fetch_dams.py) ซึ่งเทียบ RID / HII / EGAT ให้แล้ว
   - กดเขื่อนบนแผนที่หรือในตาราง -> ไฮไลต์กรอบอำเภอท้ายน้ำบนแผนที่ แยก 3 ระดับตามลำน้ำ
     (นิยามอยู่ใน dam_zones.py, ขอบเขตอำเภอจาก data/geo/districts.json ของ geo_prep.py)
   - กราฟ % ความจุย้อนหลัง 120 วัน เทียบช่วงเดียวกันปีที่แล้ว จาก data/dam_history.json
   - เส้นทางน้ำจริงจากเขื่อนถึงปลายน้ำ (river_routes.py -> data/geo/routes.json) วาดเป็นเส้นไหล + ลูกศร
   - ธงภัยที่สถานีวัดระดับน้ำริมแม่น้ำ 3 สี (fetch_flags.py -> data/river_flags.json)

   trackpad: สองนิ้วเลื่อน = เลื่อนหน้า, ถ่างนิ้ว/Ctrl+เลื่อน = ซูมแผนที่
   (Leaflet 1.9.4 ไม่รองรับ scrollWheelZoom:'ctrl' จึงปิด wheel zoom แล้วดักเอง)"""
import json, os, sys, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from dam_zones import zone_for
from dam_forecast import forecast, backtest

V = json.load(open(os.path.join(BASE, "data", "dams_verified.json")))
H = json.load(open(os.path.join(BASE, "data", "dam_history.json")))
GEO = json.load(open(os.path.join(BASE, "data", "geo", "districts.json")))


def optional(*path, default=None):
    f = os.path.join(BASE, *path)
    return json.load(open(f)) if os.path.exists(f) else default


ROUTES = optional("data", "geo", "routes.json", default={})
UP = optional("data", "geo", "upstream.json", default={"dams": {}, "basin": None})
FH = optional("data", "flag_history.json", default={})
FLAGS = optional("data", "river_flags.json", default={"flags": [], "fetched_at": None})

geo_idx = {(v["p"], v["a"]): code for code, v in GEO.items()}
used = set()
today = V["rid_date"] or datetime.date.today().isoformat()
ly_today = str(int(today[:4]) - 1) + today[4:]
hist_dates = sorted(H)
TODAY = datetime.date.fromisoformat(today)
recent = [d for d in hist_dates if d > (TODAY - datetime.timedelta(days=120)).isoformat()]
past = [d for d in hist_dates if d not in recent]  # ช่วงเดียวกันของปีที่แล้ว


# ---- คาดการ 30 วัน + ทดสอบย้อนหลัง (dam_forecast.py) ----
SER, LY = {}, {}
for dt in hist_dates:
    for n, v in H[dt].items():
        if v[0] is None:
            continue
        if dt in recent:
            SER.setdefault(n, {})[dt] = v[0]
        else:
            LY.setdefault(n, {})[str(int(dt[:4]) + 1) + dt[4:]] = v[0]
origins = [d for d in recent if TODAY - datetime.date.fromisoformat(d) >= datetime.timedelta(days=30)]
BT = backtest(SER, LY, origins)
ERR = {h: v["model"] for h, v in BT.items()}


def series(name, dates):
    return [[d, H[d][name][0]] for d in dates if name in H[d] and H[d][name][0] is not None]


def value_on(name, d):
    return (H.get(d) or {}).get(name)


dams = []
for d in V["dams"]:
    if d["lat"] is None:
        continue
    z = zone_for(d["name"])
    reaches = []
    if z:
        for r in z["reaches"]:
            codes = []
            for pro, amps in r["areas"].items():
                for a in amps:
                    c = geo_idx.get((pro, a))
                    if c:
                        codes.append(c)
                        used.add(c)
            reaches.append({"tier": r["tier"], "label": r["label"], "lag": r["lag"], "codes": codes})
    nm = d["name"]
    hs = series(nm, recent)
    # ช่วงเดียวกันปีที่แล้ว: เลื่อนวันที่ +1 ปีให้วางทับแกนเดียวกันได้
    ly = [[str(int(p[0][:4]) + 1) + p[0][4:], p[1]] for p in series(nm, past)]
    lyv = value_on(nm, ly_today)
    d7 = value_on(nm, (TODAY - datetime.timedelta(days=7)).isoformat())
    # อัตราเปลี่ยนจริงเฉลี่ย 7 วัน (ล้าน ลบ.ม./วัน) นิ่งกว่า inflow-outflow วันเดียว
    rate7 = round((d["volume"] - d7[1]) / 7, 2) if d7 and d7[1] is not None and d["volume"] is not None else None
    dams.append({
        **{k: d[k] for k in ("name", "region", "owner", "basin", "province", "lat", "lon", "normal",
                             "capacity", "dead", "volume", "pct", "active", "room", "inflow", "outflow",
                             "spill", "urc_pct", "lrc_pct", "run_of_river", "primary", "sources",
                             "verdict")},
        "d7": round(d["pct"] - d7[0], 2) if d7 and d7[0] is not None and d["pct"] is not None else None,
        "ly": lyv[0] if lyv else None, "rate7": rate7,
        "hist": hs, "hist_ly": ly, "routes": ROUTES.get(nm, []),
        "fc": forecast(SER.get(nm, {}), LY.get(nm, {}), today,
                       (d["dead"] or 0) / d["normal"] * 100 if d["normal"] else 0,
                       (d["capacity"] or d["normal"] * 1.2) / d["normal"] * 100 if d["normal"] else 120, ERR)
              if d["normal"] and nm in SER else [],
        "up": UP["dams"].get(nm),
        "zone": {"river": z["river"], "home": z["home"], "home_note": z["home_note"],
                 "conf": z["conf"], "reaches": reaches} if z else None})

geo_used = {c: GEO[c] for c in sorted(used)}
home_code = geo_idx.get(("กรุงเทพมหานคร", "สายไหม"))
if home_code:
    geo_used[home_code] = GEO[home_code]

# ประวัติธง: % ตลิ่งสูงสุดรายวัน เรียงตาม FDATES (ย้อนหลังสูงสุด 90 วัน)
FDATES = sorted({dt for h in FH.values() for dt in h if dt <= today})
flags = []
for f in FLAGS["flags"]:
    h = FH.get(str(f.get("id")), {})
    flags.append({**{k: f.get(k) for k in ("name", "code", "river", "lat", "lon", "sev", "msl", "bank", "lb", "rb",
                                            "pct", "trend", "dt", "suspect", "agency", "pro", "amp", "reg")},
                  "geo": geo_idx.get((f["pro"], f["amp"])), "h": [h.get(dt) for dt in FDATES]})

DATA = {"t_start": recent[0] if recent else today, "fdates": FDATES, "bt": BT, "basin": UP.get("basin"),
        "flags": flags, "flags_at": FLAGS["fetched_at"], "fetched_at": V["fetched_at"], "rid_date": V["rid_date"], "egat_date": V["egat_date"],
        "errors": V["errors"], "today": today, "dams": dams, "geo": geo_used,
        "home": [13.9175, 100.6512], "home_code": home_code}

HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>เขื่อนทั่วประเทศ</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1c1c1a;--sub:#5f5f5a;--mut:#8a8a84;--line:#e4e3de;
--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;
--t1:#184f95;--t2:#3987e5;--t3:#86b6ef;--ly:#a8a8a2;--link:#256abf;--flow:#0d366b;--upf:#2a78d6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--card:#1a1a19;--ink:#ededea;
--sub:#b5b5ae;--mut:#85857f;--line:#2e2e2b;--t1:#9ec5f4;--t2:#5598e7;--t3:#256abf;--ly:#6a6a64;--link:#86b6ef;--flow:#0d366b}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--ink:#ededea;--sub:#b5b5ae;--mut:#85857f;--line:#2e2e2b;
--t1:#9ec5f4;--t2:#5598e7;--t3:#256abf;--ly:#6a6a64;--link:#86b6ef;--flow:#0d366b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Sarabun","Noto Sans Thai",sans-serif;font-size:15px}
a{color:var(--link)}
.wrap{max-width:1400px;margin:0 auto;padding:14px 16px 40px}
header h1{font-size:1.35rem;margin:0 0 2px}
.mut{color:var(--mut);font-size:.8rem}.sub{color:var(--sub)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px}
.kpi .v{font-size:1.5rem;font-weight:700;font-variant-numeric:tabular-nums}
.kpi .l{font-size:.8rem;color:var(--sub)}
.main{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(320px,1fr);gap:12px}
@media (max-width:900px){.main{grid-template-columns:1fr}}
#map{height:640px;border-radius:12px;border:1px solid var(--line)}
@media (max-width:900px){#map{height:460px}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
#panel{max-height:640px;overflow:auto}
#panel h2{margin:0;font-size:1.2rem}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:.78rem;padding:2px 9px;border-radius:999px;
border:1px solid var(--line);white-space:nowrap}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;margin:10px 0;font-size:.88rem}
.stats b{font-variant-numeric:tabular-nums}
.sec{font-weight:700;font-size:.9rem;margin:14px 0 4px}
.reach{border-left:4px solid var(--t2);padding:2px 0 2px 9px;margin:6px 0;font-size:.86rem}
.reach .am{color:var(--sub);font-size:.8rem;line-height:1.55}
.am span{cursor:pointer;border-bottom:1px dotted var(--mut)}
.am span:hover{color:var(--link)}
table.src{border-collapse:collapse;width:100%;font-size:.8rem}
table.src td,table.src th{padding:3px 6px;border-bottom:1px solid var(--line);text-align:right}
table.src td:first-child,table.src th:first-child{text-align:left}
.tools{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
button{font:inherit;font-size:.82rem;background:var(--card);color:var(--ink);border:1px solid var(--line);
border-radius:8px;padding:5px 11px;cursor:pointer}
button:hover{border-color:var(--link)}button.on{background:var(--t1);color:#fff;border-color:var(--t1)}
#legend{font-size:.78rem;display:flex;gap:14px;flex-wrap:wrap;margin-top:8px;color:var(--sub)}
#legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-1px}
.tbl{overflow-x:auto;margin-top:14px}
table.dams{border-collapse:collapse;width:100%;font-size:.85rem;min-width:900px}
table.dams th{font-weight:600;color:var(--sub);text-align:right;padding:6px 8px;border-bottom:1px solid var(--line);
cursor:pointer;white-space:nowrap;position:sticky;top:0;background:var(--card)}
table.dams td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
table.dams th:nth-child(-n+2),table.dams td:nth-child(-n+2){text-align:left}
table.dams tr.row{cursor:pointer}table.dams tr.row:hover td{background:rgba(57,135,229,.08)}
table.dams tr.selrow td{background:rgba(57,135,229,.16)}
tr.grp td{font-weight:700;background:var(--bg);text-align:left}
.bar{position:relative;height:10px;width:110px;background:var(--line);border-radius:3px;display:inline-block;vertical-align:middle;margin-right:6px}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:3px}
.bar u{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--ink)}
#chart svg{width:100%;height:auto;display:block}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:4px 8px;font-size:.78rem;box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;z-index:5}
.leaflet-container{font:inherit;background:var(--bg)}
.foot{margin-top:22px;line-height:1.7}
.ico{background:none;border:none}
.ico svg{display:block;overflow:visible;filter:drop-shadow(0 0 1.5px rgba(255,255,255,.95)) drop-shadow(0 1px 2px rgba(0,0,0,.35))}
.flow{stroke-dasharray:12 10;animation:flow 1.1s linear infinite}
@keyframes flow{to{stroke-dashoffset:-22}}
@media (prefers-reduced-motion:reduce){.flow{animation:none;stroke-dasharray:none}}
.arrow{background:none;border:none}
#legend svg{vertical-align:-3px;margin-right:3px}
.lg{display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.timebar{margin-top:10px;padding:10px 14px}
.trow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tslider{flex:1;min-width:200px}
.tslider input[type=range]{width:100%;margin:0;accent-color:var(--t1);height:26px;display:block}
.tlabel{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:4px;font-size:.9rem}
.tscale{position:relative;height:16px;font-size:.72rem;color:var(--mut);margin:0 8px}
.tscale span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.kind-obs{background:var(--t1);color:#fff;border-color:var(--t1)}
.kind-fc{background:repeating-linear-gradient(45deg,var(--t3),var(--t3) 4px,var(--card) 4px,var(--card) 8px);color:var(--ink);border-color:var(--t2)}
#mapdate{position:absolute;top:10px;left:10px;z-index:500;background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:4px 10px;font-size:.85rem;box-shadow:0 2px 8px rgba(0,0,0,.12);pointer-events:none}
.mapwrap{position:relative}
select{font:inherit;font-size:.82rem;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:5px 8px}
table.prov{border-collapse:collapse;width:100%;font-size:.82rem}
table.prov td,table.prov th{padding:3px 6px;border-bottom:1px solid var(--line);text-align:right}
table.prov td:first-child,table.prov th:first-child{text-align:left}
.flagrow{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid var(--line);font-size:.84rem;cursor:pointer}
</style>
</head>
<body>
<div class="wrap">
<header style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
  <div><h1>สถานะเขื่อนใหญ่ทั่วประเทศ</h1>
  <div class="mut" id="stamp"></div></div>
  <a href="saimai-forecast.html" class="card" style="text-decoration:none;color:var(--ink);padding:8px 14px;border-color:var(--t2)">
    <b>▶ สายไหม · ลำลูกกา 14 วันข้างหน้า</b><br><span class="mut">แอนิเมชันผลกระทบ + พยากรณ์ระดับน้ำ (ซม.)</span></a>
  <a href="north-water.html" class="card" style="text-decoration:none;color:var(--ink);padding:8px 14px;border-color:var(--t2)">
    <b>▶ น้ำเหนือไปไหน</b><br><span class="mut">ทำไมไม่ทำให้สายไหมท่วมเพิ่ม · ใครได้รับผลจริง</span></a>
</header>

<div class="kpis" id="kpis"></div>

<div class="main">
  <div>
    <div class="mapwrap"><div id="map"></div><div id="mapdate"></div></div>
    <div class="card timebar">
      <div class="trow">
        <button id="tPlay" title="เล่นต่อเนื่อง">▶ เล่น</button>
        <button id="tPrev">◀ 1 วัน</button>
        <div class="tslider"><input type="range" id="tRange" aria-label="เลือกวันที่"><div class="tscale" id="tScale"></div></div>
        <button id="tNext">1 วัน ▶</button>
        <button id="tToday">วันนี้</button>
      </div>
      <div class="tlabel"><b id="tDate"></b><span class="badge" id="tKind"></span><span class="mut" id="tNote"></span></div>
    </div>
    <div class="tools">
      <button id="bBasin">ลุ่มเจ้าพระยาทั้งระบบ (เหนือ → กทม.)</button>
      <button id="bAll">ไฮไลต์ท้ายน้ำของเขื่อนที่ ≥ 95%</button>
      <button id="bClear">ล้างไฮไลต์</button>
    </div>
    <div class="tools">
      <span class="mut" style="align-self:center">ธงภัย พื้นที่:</span>
      <select id="area"></select>
      <span class="mut" style="align-self:center;margin-left:6px">แสดง:</span>
      <button data-fm="auto" class="on" title="ยังไม่เลือกเขื่อน: แสดงธงแดง+เหลือง · เลือกเขื่อนแล้ว: เฉพาะสถานีท้ายน้ำทุกสี">อัตโนมัติ</button>
      <button data-fm="all">ทุกสถานี</button>
      <button data-fm="none">ซ่อน</button>
    </div>
    <div id="legend">
      <div class="lg"><b>เขื่อน</b><span id="lgDam"></span></div>
      <div class="lg"><b>ธงภัย</b> (สถานีวัดระดับน้ำริมแม่น้ำ)<span id="lgFlag"></span></div>
      <div class="lg"><b>ต้นน้ำ</b>
        <span><svg width="30" height="10"><line x1="1" y1="5" x2="22" y2="5" stroke="var(--upf)" stroke-width="3" stroke-dasharray="7 5"/><path d="M21 1 L29 5 L21 9Z" fill="var(--upf)"/></svg>ลำน้ำที่ไหลเข้าเขื่อน (HydroRIVERS) ความหนา = ขนาดพื้นที่รับน้ำ</span></div>
      <div class="lg"><b>ท้ายน้ำ</b>
        <span><svg width="30" height="10"><line x1="1" y1="5" x2="22" y2="5" stroke="var(--flow)" stroke-width="3" stroke-dasharray="7 5"/><path d="M21 1 L29 5 L21 9Z" fill="var(--flow)"/></svg>ทิศทางน้ำจริงตามแม่น้ำ</span>
        <span><svg width="26" height="10"><line x1="1" y1="5" x2="25" y2="5" stroke="var(--flow)" stroke-width="3" stroke-dasharray="2 5" opacity=".55"/></svg>ช่วงประมาณ (เส้นแม่น้ำ OSM ขาด)</span>
        <span><i style="background:var(--t1)"></i>ท้ายเขื่อนทันที</span>
        <span><i style="background:var(--t2)"></i>ตามลำน้ำ</span>
        <span><i style="background:var(--t3)"></i>ปลายทาง</span>
        <span><i style="background:transparent;border:2px dashed var(--ink)"></i>บ้าน (สายไหม)</span></div>
    </div>
    <div class="mut" style="margin-top:4px">trackpad: สองนิ้วเลื่อน = เลื่อนหน้า · ถ่างนิ้ว หรือกด Ctrl/Cmd ค้างแล้วเลื่อน = ซูม · ลาก = เลื่อนแผนที่</div>
  </div>
  <div class="card" id="panel"></div>
</div>

<div class="card tbl">
  <div class="sec" style="margin-top:0">ทุกเขื่อน (กดหัวคอลัมน์เพื่อเรียง · กดแถวเพื่อดูบนแผนที่)</div>
  <table class="dams" id="tbl"></table>
</div>

<div class="mut foot">
<b>แหล่งข้อมูลและการเทียบ</b> ทุกเขื่อนดึงพร้อมกันจาก 3 แหล่ง:
RID = กรมชลประทาน <a href="https://app.rid.go.th/reservoir/">app.rid.go.th/reservoir</a> (ต้นทาง 35 เขื่อน) ·
HII = สสน. <a href="https://www.thaiwater.net/">thaiwater.net</a> (ตัวรวบรวม) ·
EGAT = กฟผ. <a href="https://water.egat.co.th/">water.egat.co.th</a> (ต้นทาง 11 เขื่อนผลิตไฟฟ้า + rule curve).
"ตรงกัน" = ปริมาตรต่างกันไม่เกิน 1.5% (หรือ 0.5 ล้าน ลบ.ม.)<br>
<b>% ความจุ</b> = ปริมาตรน้ำ ÷ ความจุที่ระดับเก็บกักปกติ (รนก.) เกิน 100% ได้เพราะอ่างรับได้ถึงระดับเก็บกักสูงสุด ·
<b>URC</b> (upper rule curve) = เกณฑ์บนของ กฟผ. ตามฤดูกาล เกินแล้วต้องเร่งระบาย<br>
<b>พื้นที่ท้ายน้ำ</b> ไล่ตามลำน้ำจริงระดับอำเภอ เป็นความสัมพันธ์ทางภูมิศาสตร์ ไม่ใช่พยากรณ์ว่าจะท่วม
ช่วงเวลาเดินทางของน้ำเป็นค่าประมาณจากระยะทาง ขอบเขตอำเภอ: OpenGISData-Thailand (กรมการปกครอง) ·
<b>ธงภัย</b> = สถานีวัดระดับน้ำโทรมาตร (thaiwater: RID/HII/EGAT/กองทัพเรือ) สีตามเกณฑ์ของ thaiwater:
เขียว ≤ 70% ของความลึกตลิ่ง · เหลือง 70-100% · แดง เกินตลิ่ง · ไม่ปักธงถ้าข้อมูลเก่ากว่า 24 ชม. ·
ธงอยู่ริมแม่น้ำ ไม่ใช่ที่เขื่อน จึงมีหลายจุดที่ไม่มีเขื่อนอยู่ใกล้<br>
<b>เส้นทางน้ำ</b> ท้ายน้ำ = shortest path บนเส้นแม่น้ำ OpenStreetMap ผ่านจุดบรรจบถึงปลายน้ำ ·
ต้นน้ำ/ทั้งลุ่ม = HydroRIVERS v10 (HydroSHEDS, Lehner &amp; Grill 2013) ไล่ย้อนตามทิศการไหล (NEXT_DOWN) ·
แนวคิดโครงข่ายลำน้ำจากต้นน้ำสู่ทะเลได้จาก <a href="https://www.meanam.com/">meanam.com</a> · ลูกศร/เส้นเคลื่อนไหว = ทิศที่น้ำไหล<br>
<b>ตัวเลื่อนเวลา</b> ย้อนหลัง = ข้อมูลจริงรายวัน (เขื่อน: RID 120 วัน · ธง: ระดับสูงสุดของวันจาก thaiwater waterlevel_graph) ·
ล่วงหน้า 30 วัน = <b>คาดการเชิงสถิติ</b> เฉพาะ % ความจุเขื่อน: เฉลี่ยของ (ก) แนวโน้ม 7 วันที่อ่อนลงครึ่งหนึ่งทุก 10 วัน
และ (ข) รูปแบบช่วงเดียวกันปีที่แล้ว ไม่รู้ฝนล่วงหน้าและไม่รู้แผนระบายของหน่วยงาน · <span id="btNote"></span> ·
ธงภัยไม่มีพยากรณ์รายสถานี วันในอนาคตจึงแสดงค่าล่าสุดแบบจาง ·
<a href="dashboard-saimai.html">dashboard ระดับน้ำสายไหม</a>
</div>
</div>
<div class="tip" id="tip"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
const $ = id => document.getElementById(id);
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const f0 = v => v == null ? '–' : Math.round(v).toLocaleString('th-TH');
const f1 = v => v == null ? '–' : (+v).toLocaleString('th-TH', {maximumFractionDigits: 1, minimumFractionDigits: 1});
const f2 = v => v == null ? '–' : (+v).toLocaleString('th-TH', {maximumFractionDigits: 2, minimumFractionDigits: 2});
const THM = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const thd = d => { const [y, m, dd] = d.split('-').map(Number); return dd + ' ' + THM[m - 1] + ' ' + (y + 543) };

function statusP(p, d) {
  if (d && d.run_of_river) return {c: css('--mut'), t: 'ฝายน้ำล้น (ไม่เก็บน้ำ)'};
  if (p == null) return {c: css('--mut'), t: 'ไม่มีข้อมูลวันนี้'};
  if (p > 100) return {c: css('--crit'), t: 'เกินระดับเก็บกักปกติ'};
  if (p >= 80) return {c: css('--warn'), t: 'เฝ้าระวัง'};
  return {c: css('--good'), t: 'ปกติ'};
}
const status = d => statusP(d.pct, d);

// ---------- เวลา: off = จำนวนวันจากวันนี้ (ลบ = ย้อนหลัง, บวก = คาดการ) ----------
const DAY = 864e5, UT = s => Date.parse(s + 'T00:00:00Z'), iso = t => new Date(t).toISOString().slice(0, 10);
const T0 = UT(D.today), MINOFF = Math.round((UT(D.t_start) - T0) / DAY), MAXOFF = 30;
let off = 0;
const curDate = () => iso(T0 + off * DAY);
const FIDX = {}; D.fdates.forEach((d, i) => FIDX[d] = i);
D.dams.forEach(d => { d.hm = {}; d.hist.forEach(p => d.hm[p[0]] = p[1]); d.fm = {}; d.fc.forEach(p => d.fm[p[0]] = p) });
function damAt(d) {        // {p, lo, hi, kind}
  if (d.run_of_river) return {p: null, kind: 'obs'};
  const dt = curDate();
  if (off <= 0) return {p: off === 0 ? d.pct : d.hm[dt], kind: 'obs'};
  const f = d.fm[dt];
  return f ? {p: f[1], lo: f[2], hi: f[3], kind: 'fc'} : {p: null, kind: 'fc'};
}
const sevOf = p => p == null ? null : p > 100 ? 2 : p >= 70 ? 1 : 0;
function flagAt(f) {       // {sev, pct, stale}
  if (off === 0) return {sev: f.sev, pct: f.pct};
  if (off > 0) return {sev: f.sev, pct: f.pct, stale: true};
  const i = FIDX[curDate()], p = i == null ? null : f.h[i];
  return {sev: sevOf(p), pct: p};
}
const verdictTxt = d => d.verdict === 'agree' ? '✓ ตรงกัน ' + Object.keys(d.sources).length + ' แหล่ง'
  : d.verdict === 'differ' ? '⚠ แหล่งข้อมูลไม่ตรงกัน' : 'แหล่งเดียว (' + d.primary + ')';

// ---------- header + KPI ----------
$('stamp').textContent = 'ข้อมูลวันที่ ' + thd(D.today) + ' · ดึงล่าสุด ' + D.fetched_at.slice(0, 16).replace('T', ' ') +
  (Object.keys(D.errors).length ? ' · ดึงไม่สำเร็จ: ' + Object.keys(D.errors).join(', ') : '');
(function kpis() {
  const st = D.dams.filter(d => !d.run_of_river && d.volume != null && d.normal);
  const vol = st.reduce((s, d) => s + d.volume, 0), nor = st.reduce((s, d) => s + d.normal, 0);
  const lyd = st.filter(d => d.ly != null);
  const lyVol = lyd.reduce((s, d) => s + d.ly / 100 * d.normal, 0), lyNor = lyd.reduce((s, d) => s + d.normal, 0);
  const over = st.filter(d => d.pct > 100), warn = st.filter(d => d.pct >= 80 && d.pct <= 100);
  const urc = st.filter(d => d.urc_pct != null && d.pct > d.urc_pct);
  const ok = D.dams.filter(d => d.verdict === 'agree').length;
  const k = [
    [f0(vol) + ' <span style="font-size:.9rem">ล้าน ลบ.ม.</span>', 'น้ำในเขื่อนใหญ่รวม = ' + f1(vol / nor * 100) +
      '% ของ รนก. (ปีที่แล้ววันเดียวกัน ' + f1(lyVol / lyNor * 100) + '%)'],
    [over.length, 'เขื่อนเกิน 100%' + (over.length ? ': ' + over.map(d => d.name).join(', ') : '')],
    [warn.length, 'เขื่อน 80-100% (เฝ้าระวัง)'],
    [urc.length, 'เขื่อน กฟผ. เกินเกณฑ์บน URC' + (urc.length ? ': ' + urc.map(d => d.name).join(', ') : '')],
    [D.flags.filter(f => f.sev === 2).length + ' <span style="font-size:.9rem">/ ' + D.flags.filter(f => f.sev === 1).length + '</span>',
      'ธงแดง ล้นตลิ่ง / ธงเหลือง เฝ้าระวัง จาก ' + D.flags.length + ' สถานี'],
    [ok + '/' + D.dams.length, 'เขื่อนที่ข้อมูลตรงกัน ≥ 2 แหล่ง'],
  ];
  $('kpis').innerHTML = k.map(x => '<div class="kpi"><div class="v">' + x[0] + '</div><div class="l">' + x[1] + '</div></div>').join('');
})();

// ---------- map ----------
const map = L.map('map', {scrollWheelZoom: false, zoomControl: false}).setView([13.4, 101.0], 6);
L.control.zoom({position: 'bottomright'}).addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 13, attribution: '&copy; OpenStreetMap'}).addTo(map);
let wheelAcc = 0;
map.getContainer().addEventListener('wheel', e => {
  if (!e.ctrlKey) return;               // สองนิ้วเลื่อน: ปล่อยให้หน้าเลื่อน
  e.preventDefault();
  wheelAcc += e.deltaY;
  if (Math.abs(wheelAcc) >= 20) {
    map.setZoomAround(map.mouseEventToContainerPoint(e), map.getZoom() + (wheelAcc > 0 ? -1 : 1));
    wheelAcc = 0;
  }
}, {passive: false});

map.createPane('zones'); map.getPane('zones').style.zIndex = 390;
const zoneLayer = L.layerGroup().addTo(map);
if (D.home_code) L.polygon(D.geo[D.home_code].g, {color: css('--ink'), weight: 2, dashArray: '5 4',
  fill: false, interactive: false}).addTo(map);
L.circleMarker(D.home, {radius: 5, color: '#fff', weight: 2, fillColor: '#1c1c1a', fillOpacity: 1})
  .bindTooltip('บ้าน (ซอยสายไหม 44)').addTo(map);

// ---------- ไอคอน: เขื่อน (กำแพง+น้ำ) และธง 3 สี ----------
// เขื่อน = วงกลมสีสถานะ + กำแพงเขื่อนกับคลื่นน้ำสีขาว (รูปทรงต่างจากธงชัดเจน)
const damSvg = (c, px) => '<svg width="' + px + '" height="' + px + '" viewBox="0 0 24 24">' +
  '<circle cx="12" cy="12" r="11" fill="' + c + '" stroke="#1c1c1a" stroke-width="1.2"/>' +
  '<path d="M5.5 18 L8.5 6 H11.5 V18 Z" fill="#fff"/>' +
  '<path d="M13 10.5 q1.3 -1.1 2.6 0 t2.6 0 M13 14 q1.3 -1.1 2.6 0 t2.6 0 M13 17.5 q1.3 -1.1 2.6 0 t2.6 0" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/></svg>';
const flagSvg = (c, px) => '<svg width="' + px + '" height="' + px + '" viewBox="0 0 24 24">' +
  '<line x1="5" y1="2" x2="5" y2="23" stroke="#1c1c1a" stroke-width="2" stroke-linecap="round"/>' +
  '<path d="M6 3 L21 8 L6 13 Z" fill="' + c + '" stroke="#1c1c1a" stroke-width="1.2" stroke-linejoin="round"/></svg>';
const FLAGC = [css('--good'), css('--warn'), css('--crit')];
const FLAGT = ['ปกติ (≤ 70% ตลิ่ง)', 'เฝ้าระวัง (70-100%)', 'ล้นตลิ่ง'];
$('lgDam').innerHTML = [['--good', '&lt; 80% ปกติ'], ['--warn', '80-100% เฝ้าระวัง'], ['--crit', '&gt; 100% เกินระดับเก็บกัก']]
  .map(x => '<span style="margin-left:10px">' + damSvg(css(x[0]), 18) + x[1] + '</span>').join('');
$('lgFlag').innerHTML = FLAGT.map((t, i) => '<span style="margin-left:10px">' + flagSvg(FLAGC[i], 17) + t + '</span>').join('');

const markers = {};
let dimOthers = null;      // Set ของเขื่อนที่ต้องเด่น (โหมดลุ่ม) ที่เหลือจาง
function damIcon(d) {
  const a = damAt(d), s = statusP(a.p, d);
  const px = d.normal ? Math.round(Math.max(20, Math.min(36, 16 + Math.sqrt(d.normal) / 5))) : 20;
  return {icon: L.divIcon({className: 'ico', html: damSvg(s.c, px), iconSize: [px, px], iconAnchor: [px / 2, px / 2]}),
          tip: '<b>' + d.name + '</b> ' + (d.run_of_river ? 'ฝายน้ำล้น' : (a.p == null ? '–' : f1(a.p) + '%') +
            (a.kind === 'fc' && a.p != null ? ' (คาดการ ' + f0(a.lo) + '-' + f0(a.hi) + '%)' : '')) + ' · ' + s.t + '<br>' + thd(curDate())};
}
D.dams.forEach(d => {
  const x = damIcon(d);
  markers[d.name] = L.marker([d.lat, d.lon], {icon: x.icon, zIndexOffset: 1000, riseOnHover: true})
    .bindTooltip(x.tip).on('click', () => select(d.name, true)).addTo(map);
});
function refreshDams() {
  D.dams.forEach(d => {
    const x = damIcon(d), m = markers[d.name];
    m.setIcon(x.icon); m.setTooltipContent(x.tip);
    m.setOpacity(dimOthers && !dimOthers.has(d.name) ? .35 : 1);
  });
}

const tierCol = t => css('--t' + t);
function drawZones(list, fit) {
  zoneLayer.clearLayers();
  const best = {};      // อำเภอเดียวอยู่หลาย reach: เอา tier ที่ใกล้เขื่อนที่สุด
  list.forEach(({dam, reach}) => reach.codes.forEach(c => {
    const cur = best[c];
    if (!cur || reach.tier < cur.reach.tier) best[c] = {dam, reach, dams: new Set([dam.name, ...(cur ? cur.dams : [])])};
    else cur.dams.add(dam.name);
  }));
  const bounds = [];
  Object.entries(best).forEach(([c, v]) => {
    const g = D.geo[c]; if (!g) return;
    const p = L.polygon(g.g, {pane: 'zones', color: tierCol(v.reach.tier), weight: 1.5, fillColor: tierCol(v.reach.tier),
      fillOpacity: v.reach.tier === 1 ? .5 : v.reach.tier === 2 ? .38 : .28});
    p.bindTooltip('<b>อ.' + g.a + ' จ.' + g.p + '</b><br>' + v.reach.label + (v.reach.lag ? ' · ' + v.reach.lag : '') +
      (v.dams.size > 1 ? '<br>ท้ายน้ำของ: ' + [...v.dams].join(', ') : ''), {sticky: true});
    p.addTo(zoneLayer);
    bounds.push(p.getBounds());
  });
  if (fit && bounds.length) {
    const b = bounds.reduce((a, x) => a.extend(x), L.latLngBounds(bounds[0].getSouthWest(), bounds[0].getNorthEast()));
    list.forEach(({dam}) => b.extend([dam.lat, dam.lon]));
    map.fitBounds(b.pad(0.08));
  }
}

$('bAll').onclick = () => {
  resetLayers(); selName = null; mode = 'hot';
  if (area !== 'all') { area = 'all'; $('area').value = 'all' }
  const hot = D.dams.filter(d => d.pct >= 95 && d.zone);
  const list = [];
  hot.forEach(d => d.zone.reaches.forEach(reach => list.push({dam: d, reach})));
  drawZones(list, true);
  zoneCodes = new Set(list.flatMap(x => x.reach.codes)); renderFlags(); drawFlows(hot);
  $('bAll').classList.add('on');
  showOverview(hot);
};
$('bClear').onclick = () => { selName = null; mode = 'overview'; resetLayers(); area = 'all'; $('area').value = 'all'; renderFlags(); map.setView([13.4, 101.0], 6); showOverview() };

// ---------- ธงภัย ----------
const flagLayer = L.layerGroup().addTo(map);
let flagMode = 'auto', zoneCodes = new Set(), upCodes = new Set(), area = 'all';
// พื้นที่สำคัญสำหรับกรองธง (ชื่อภาค = geocode.area_name ของ thaiwater)
const BKK = ['กรุงเทพมหานคร', 'นนทบุรี', 'ปทุมธานี', 'สมุทรปราการ', 'สมุทรสาคร', 'นครปฐม'];
const AREAS = {
  all: {t: 'ทั้งประเทศ'},
  bkk: {t: 'กรุงเทพฯ และปริมณฑล', f: f => BKK.includes(f.pro)},
  home: {t: 'รอบบ้านสายไหม 25 กม.', f: f => L.latLng(f.lat, f.lon).distanceTo(D.home) <= 25000},
  cpylow: {t: 'เจ้าพระยาตอนล่าง (นครสวรรค์ → อยุธยา)', f: f => ['นครสวรรค์', 'อุทัยธานี', 'ชัยนาท', 'สิงห์บุรี', 'อ่างทอง', 'ลพบุรี', 'สระบุรี', 'พระนครศรีอยุธยา'].includes(f.pro)},
  cpy: {t: 'ลุ่มเจ้าพระยาทั้งลุ่ม (เหนือ → กทม.)', f: f => (D.basin && D.basin.codes.includes(f.geo)) || BKK.includes(f.pro)},
};
[...new Set(D.flags.map(f => f.reg).filter(r => r && r.startsWith('ภาค')))].sort().forEach(r => AREAS['reg:' + r] = {t: 'ภาค' + r.replace(/^ภาค/, ''), f: f => f.reg === r});
$('area').innerHTML = Object.entries(AREAS).map(([k, v]) => '<option value="' + k + '">' + v.t + '</option>').join('');
function flagTip(f) {
  const a = flagAt(f), sv = a.sev == null ? null : a.sev;
  let t = '<b>' + f.name + '</b> ' + (f.code ? '(' + f.code + ')' : '') + '<br>' + f.river + ' · อ.' + f.amp + ' จ.' + f.pro +
    '<br>' + (sv == null ? 'ไม่มีข้อมูลวันนี้' : FLAGT[sv]) + (a.pct != null ? ' · ' + f0(a.pct) + '% ของตลิ่ง' : '') +
    (off < 0 ? ' (สูงสุดของวันที่ ' + thd(curDate()) + ')' : off > 0 ? '<br>ค่าล่าสุด (ไม่มีพยากรณ์รายสถานี)' :
      '<br>ระดับ ' + f2(f.msl) + ' ม.รทก. / ตลิ่ง ' + f2(f.bank) +
      (f.trend != null ? '<br>เทียบรอบก่อน ' + (f.trend >= 0 ? '▲ +' : '▼ ') + f2(f.trend) + ' ม.' : '')) +
    '<br><span style="color:#888">' + f.agency + ' · ' + f.dt + '</span>';
  if (f.suspect) t += '<br>⚠ เกินเกณฑ์ตลิ่งของสถานี แต่ยังต่ำกว่าตลิ่งซ้าย/ขวาที่สำรวจ (' + f2(f.lb) + '/' + f2(f.rb) + ') เกณฑ์อาจผิด';
  return t;
}
const inArea = f => area === 'all' || AREAS[area].f(f);
function flagVisible(f, a) {
  if (flagMode === 'none' || a.sev == null) return false;
  if (!inArea(f)) return false;
  if (flagMode === 'all' || area !== 'all') return true;
  // auto: ภาพรวม = แดง+เหลือง, เลือกเขื่อน/ลุ่มแล้ว = ทุกสีในอำเภอท้ายน้ำและต้นน้ำ
  if (zoneCodes.size || upCodes.size) return !!f.geo && (zoneCodes.has(f.geo) || upCodes.has(f.geo));
  return a.sev >= 1;
}
function renderFlags() {
  flagLayer.clearLayers();
  const z = map.getZoom(), k = z <= 6 ? .72 : z <= 7 ? .86 : 1;
  D.flags.forEach(f => {
    const a = flagAt(f);
    if (!flagVisible(f, a)) return;
    const px = Math.round((a.sev === 2 ? 22 : a.sev === 1 ? 19 : 16) * k);
    L.marker([f.lat, f.lon], {icon: L.divIcon({className: 'ico', html: flagSvg(FLAGC[a.sev], px),
        iconSize: [px, px], iconAnchor: [px * 5 / 24, px * 23 / 24]}), zIndexOffset: a.sev * 100,
        opacity: a.stale ? .35 : f.suspect ? .55 : 1})
      .bindTooltip(flagTip(f)).addTo(flagLayer);
  });
}
document.querySelectorAll('[data-fm]').forEach(b => b.onclick = () => {
  flagMode = b.dataset.fm;
  document.querySelectorAll('[data-fm]').forEach(x => x.classList.toggle('on', x === b));
  renderFlags();
});

// ---------- เส้นทางน้ำ: เส้นไหลเคลื่อนไหว + ลูกศรตามทิศการไหล ----------
map.createPane('flow'); map.getPane('flow').style.zIndex = 420;
const flowLayer = L.layerGroup().addTo(map), arrowLayer = L.layerGroup().addTo(map), upLayer = L.layerGroup().addTo(map);
let flowLines = [], upLines = [];
// ต้นน้ำ/ทั้งลุ่ม (HydroRIVERS): ความหนาตามพื้นที่รับน้ำ ลูกศรเฉพาะสายใหญ่ ทิศ = ตามลำดับจุด (ต้นน้ำ → ท้ายน้ำ)
function drawUp(chains, refArea) {
  upLayer.clearLayers(); upLines = [];
  if (!chains) { drawArrows(); return }
  const col = css('--upf');
  chains.forEach(c => {
    const r = c.up / refArea, w = Math.max(1.2, Math.min(6, 1.2 + 4.8 * Math.sqrt(r)));
    L.polyline(c.g, {pane: 'flow', color: '#fff', weight: w + 2.5, opacity: .7, interactive: false}).addTo(upLayer);
    L.polyline(c.g, {pane: 'flow', color: col, weight: w, opacity: .9, className: r > .02 ? 'flow' : '', interactive: false})
      .bindTooltip('ลำน้ำต้นน้ำ · พื้นที่รับน้ำ ~' + f0(c.up) + ' km²', {sticky: true}).addTo(upLayer);
    if (r >= .12) upLines.push(c.g);
  });
  drawArrows();
}
function drawFlows(dams) {
  flowLayer.clearLayers(); flowLines = [];
  dams.forEach(d => (d.routes || []).forEach(r => {
    L.polyline([[d.lat, d.lon], r.line[0]], {pane: 'flow', color: css('--flow'), weight: 2, dashArray: '3 4', interactive: false}).addTo(flowLayer);
    L.polyline(r.line, {pane: 'flow', color: '#fff', weight: 8, opacity: .85, interactive: false}).addTo(flowLayer);
    L.polyline(r.line, {pane: 'flow', color: css('--flow'), weight: 4, className: 'flow', interactive: false}).addTo(flowLayer);
    // ช่วงที่เส้นแม่น้ำ OSM ขาด = ลากตรงโดยประมาณ: ลบเส้นทึบแล้ววาดเป็นเส้นประจาง
    (r.gaps || []).forEach(g => {
      L.polyline(g, {pane: 'flow', color: '#fff', weight: 9, opacity: 1, interactive: false}).addTo(flowLayer);
      L.polyline(g, {pane: 'flow', color: css('--flow'), weight: 3, opacity: .55, dashArray: '2 6', interactive: false})
        .bindTooltip('ช่วงนี้เส้นแม่น้ำใน OpenStreetMap ขาด ลากตรงโดยประมาณ (ทิศทางถูก แนวไม่ตรงลำน้ำ)', {sticky: true}).addTo(flowLayer);
    });
    flowLines.push(r.line);
  }));
  drawArrows();
}
function drawArrows() {
  arrowLayer.clearLayers();
  const GAP = 120, WIN = 28;   // ทิศของลูกศร = แนวรวมช่วง ±WIN px ไม่ใช่ส่วนโค้งเล็กๆ ของแม่น้ำคดเคี้ยว
  flowLines.map(l => [l, css('--flow'), true]).concat(upLines.map(l => [l, css('--upf'), false])).forEach(([line, col, endDot]) => {
    const pts = line.map(p => map.latLngToLayerPoint(p)), cum = [0];
    for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + pts[i - 1].distanceTo(pts[i]));
    const total = cum[cum.length - 1];
    const at = s => {
      s = Math.max(0, Math.min(total, s));
      let i = 1; while (i < cum.length - 1 && cum[i] < s) i++;
      const a = pts[i - 1], b = pts[i], t = (s - cum[i - 1]) / ((cum[i] - cum[i - 1]) || 1);
      return L.point(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t);
    };
    for (let s = 50; s < total - 20; s += GAP) {
      const p = at(s), a = at(s - WIN), b = at(s + WIN);
      const ang = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
      L.marker(map.layerPointToLatLng(p), {pane: 'flow', interactive: false, icon: L.divIcon({className: 'arrow',
        iconSize: [24, 24], iconAnchor: [12, 12],
        html: '<svg width="24" height="24" viewBox="0 0 24 24" style="transform:rotate(' + ang + 'deg);overflow:visible">' +
          '<circle cx="12" cy="12" r="10" fill="#fff" stroke="' + col + '" stroke-width="1.5"/>' +
          '<path d="M7.5 6.5 L17.5 12 L7.5 17.5 L10 12 Z" fill="' + col + '"/></svg>'})}).addTo(arrowLayer);
    }
    if (!endDot) return;
    const e = line[line.length - 1];
    L.circleMarker(e, {pane: 'flow', radius: 5, color: '#fff', weight: 2, fillColor: col, fillOpacity: 1})
      .bindTooltip('ปลายเส้นทาง').addTo(arrowLayer);
  });
}
map.on('zoomend', () => { drawArrows(); renderFlags() });

// ---------- side panel ----------
function showOverview(hot) {
  let h = '<h2>' + (hot ? 'เขื่อนที่ ≥ 95% และพื้นที่ท้ายน้ำ' : 'เลือกเขื่อน') + '</h2>';
  if (!hot) {
    h += '<p class="sub" style="font-size:.9rem">กดวงกลมบนแผนที่ หรือกดแถวในตารางด้านล่าง ' +
      'แผนที่จะไฮไลต์กรอบอำเภอท้ายน้ำของเขื่อนนั้น แยกสีตามระยะ: เข้ม = ท้ายเขื่อนทันที, กลาง = ตามลำน้ำ, อ่อน = ปลายทาง</p>' +
      '<p class="sub" style="font-size:.9rem">ขนาดวงกลม = ขนาดอ่าง · สี = % ความจุ</p>';
    const top = D.dams.filter(d => d.pct != null && !d.run_of_river).sort((a, b) => b.pct - a.pct).slice(0, 8);
    h += '<div class="sec">% ความจุสูงสุด 8 อันดับ</div>' + top.map(d => row(d)).join('');
  } else {
    h += '<p class="sub" style="font-size:.88rem">' + hot.length + ' เขื่อน · กดชื่อเพื่อดูรายละเอียด</p>' + hot.map(d => row(d)).join('');
  }
  $('panel').innerHTML = h;
  $('panel').querySelectorAll('[data-dam]').forEach(e => e.onclick = () => select(e.dataset.dam, true));
}
function row(d) {
  const s = status(d);
  return '<div data-dam="' + d.name + '" style="cursor:pointer;display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid var(--line);font-size:.88rem">' +
    '<span><span class="dot" style="background:' + s.c + '"></span> ' + d.name + ' <span class="mut">' + d.province + '</span></span>' +
    '<b style="font-variant-numeric:tabular-nums">' + f1(d.pct) + '%</b></div>';
}

let selName = null, mode = 'overview';
function resetLayers() {
  zoneLayer.clearLayers(); zoneCodes = new Set(); upCodes = new Set(); dimOthers = null;
  drawFlows([]); drawUp(null); refreshDams();
  ['bAll', 'bBasin'].forEach(k => $(k).classList.remove('on'));
  document.querySelectorAll('#tbl tr.selrow').forEach(r => r.classList.remove('selrow'));
}
function select(name, fit) {
  const d = D.dams.find(x => x.name === name); if (!d) return;
  selName = name; mode = 'dam'; dimOthers = null;
  $('bAll').classList.remove('on'); $('bBasin').classList.remove('on');
  if (area !== 'all') { area = 'all'; $('area').value = 'all' }
  document.querySelectorAll('#tbl tr.row').forEach(r => r.classList.toggle('selrow', r.dataset.dam === name));
  if (d.zone) drawZones(d.zone.reaches.map(reach => ({dam: d, reach})), fit);
  else { zoneLayer.clearLayers(); if (fit) map.setView([d.lat, d.lon], 9) }
  zoneCodes = new Set(d.zone ? d.zone.reaches.flatMap(r => r.codes) : []);
  upCodes = new Set(d.up ? d.up.codes : []);
  drawFlows([d]); drawUp(d.up && d.up.chains, d.up ? d.up.area_km2 : 1);
  if (fit && d.up && d.up.chains.length) {   // ให้เห็นทั้งต้นน้ำและท้ายน้ำ
    const b = L.latLngBounds([[d.lat, d.lon]]);
    d.up.chains.forEach(c => c.g.forEach(p => b.extend(p)));
    (d.routes || []).forEach(r => r.line.forEach(p => b.extend(p)));
    map.fitBounds(b.pad(0.05));
  }
  refreshDams(); renderFlags();
  const s = status(d), z = d.zone;
  let h = '<div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">' +
    '<div><h2>เขื่อน' + d.name + '</h2><div class="mut">' + [d.owner, d.basin, 'จ.' + d.province].filter(Boolean).join(' · ') + '</div></div>' +
    '<button onclick="clearSel()">ปิด</button></div>';
  h += '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">' +
    '<span class="badge"><span class="dot" style="background:' + s.c + '"></span>' + s.t + '</span>' +
    '<span class="badge">' + verdictTxt(d) + '</span>' +
    (d.urc_pct != null ? '<span class="badge">' + (d.pct > d.urc_pct ? '⚠ เกิน' : 'ต่ำกว่า') + ' URC (' + f1(d.urc_pct) + '%)</span>' : '') + '</div>';
  if (!d.run_of_river) {
    const rate = d.rate7;
    let eta = '–';
    if (d.room <= 0) eta = 'เกินแล้ว ' + f1(-d.room) + ' ล้าน ลบ.ม.';
    else if (rate > 0) eta = '~' + Math.ceil(d.room / rate) + ' วัน';
    else if (rate != null) eta = 'ไม่ถึง (7 วันที่ผ่านมาน้ำลด/ทรงตัว)';
    h += '<div id="tnow" class="card" style="margin-top:10px;padding:8px 12px"></div>';
    h += '<div class="stats">' +
      '<div>% ความจุวันนี้ (รนก.)<br><b style="font-size:1.35rem">' + f1(d.pct) + '%</b></div>' +
      '<div>เทียบ 7 วันก่อน / ปีที่แล้ว<br><b>' + (d.d7 == null ? '–' : (d.d7 >= 0 ? '+' : '') + f1(d.d7)) + '</b> จุด · <b>' + f1(d.ly) + '%</b></div>' +
      '<div>ปริมาตร<br><b>' + f0(d.volume) + '</b> / ' + f0(d.normal) + ' ล้าน ลบ.ม.</div>' +
      '<div>น้ำใช้การได้<br><b>' + f0(d.active) + '</b> ล้าน ลบ.ม.</div>' +
      '<div>ไหลเข้า / ระบาย (ต่อวัน)<br><b>' + f2(d.inflow) + ' / ' + f2(d.outflow) + '</b> ล้าน ลบ.ม.</div>' +
      '<div>เปลี่ยนเฉลี่ย 7 วัน<br><b>' + (rate == null ? '–' : (rate >= 0 ? '+' : '') + f2(rate)) + '</b> ล้าน ลบ.ม./วัน</div>' +
      '<div>ถึง 100% ถ้าเพิ่มในอัตรานี้<br><b>' + eta + '</b></div></div>';
  }
  h += '<div class="sec">% ความจุ 120 วัน + คาดการ 30 วัน เทียบปีที่แล้ว</div><div id="chart" style="position:relative"></div>' +
    '<div class="mut"><span style="color:var(--t1)">━</span> ปีนี้ (จริง) · <span style="color:var(--t2)">┅</span> คาดการ + แถบช่วง · ' +
    '<span style="color:var(--ly)">┅</span> ปีที่แล้ว · เส้นแดงประ = 100% · เส้นตั้ง = วันที่เลือก' +
    (d.urc_pct != null ? ' · ◆ = URC วันนี้' : '') + '</div>';
  if (d.up) {
    const ufl = D.flags.filter(f => f.geo && upCodes.has(f.geo) && !zoneCodes.has(f.geo));
    h += '<div class="sec">ต้นน้ำ: น้ำที่เข้าอ่างมาจากไหน</div><div class="sub" style="font-size:.85rem">พื้นที่รับน้ำ ~' + f0(d.up.area_km2) +
      ' km² · ลำน้ำสายหลักผ่าน ' + d.up.codes.length + ' อำเภอ' +
      (d.up.up_dams.length ? ' · เขื่อนต้นน้ำ: ' + d.up.up_dams.map(n => '<a href="#" data-dam="' + n + '">' + n + '</a>').join(', ') : '') +
      '<br><span class="mut">ภาพจาก HydroRIVERS ไล่ย้อนทิศการไหล ความหนาเส้น = ขนาดพื้นที่รับน้ำ</span></div>' +
      '<div id="upflags"></div>';
  }
  if (z) {
    const rk = (d.routes || []).map(r => '~' + f0(r.km) + ' กม.' + (r.gaps && r.gaps.length ? ' (มีช่วงประมาณ)' : '')).join(' / ');
    h += '<div class="sec">พื้นที่ท้ายน้ำ (ไฮไลต์บนแผนที่)</div><div class="mut">เส้นทางน้ำ: ' + z.river +
      (rk ? ' · ระยะตามลำน้ำ ' + rk : '') +
      (z.conf === 'medium' ? ' · เขื่อนขนาดกลาง/ลำน้ำสาขา เส้นทางโดยประมาณ' : '') + '</div>';
    z.reaches.forEach(r => {
      h += '<div class="reach" style="border-color:' + tierCol(r.tier) + '"><b>' + r.label + '</b>' +
        (r.lag ? ' <span class="mut">' + r.lag + '</span>' : '') + '<div class="am">' +
        r.codes.map(c => '<span data-c="' + c + '">' + D.geo[c].a + '</span>').join(' · ') + '</div></div>';
    });
    h += '<div class="sec">ธงภัยท้ายน้ำ</div><div id="zflags"></div>';
    h += '<div class="sec">ผลต่อบ้าน (ซอยสายไหม 44): ' + z.home + '</div><div class="sub" style="font-size:.84rem">' + z.home_note + '</div>';
  }
  h += '<div class="sec">เทียบแหล่งข้อมูล</div><table class="src"><tr><th>แหล่ง</th><th>วันที่</th><th>ปริมาตร</th><th>%</th><th>เข้า</th><th>ออก</th></tr>';
  Object.entries(d.sources).forEach(([k, v]) => {
    h += '<tr><td>' + k + (k === d.primary ? ' (หลัก)' : '') + (v.agency && k === 'HII' ? ' <span class="mut">แถว ' + v.agency + '</span>' : '') +
      '</td><td>' + (v.date || '–') + '</td><td>' + f2(v.volume) + '</td><td>' + f1(v.pct) + '</td><td>' + f2(v.inflow) + '</td><td>' + f2(v.outflow) + '</td></tr>';
  });
  h += '</table>';
  $('panel').innerHTML = h;
  $('panel').scrollTop = 0;
  $('panel').querySelectorAll('[data-c]').forEach(e => e.onclick = () => {
    const g = D.geo[e.dataset.c]; map.fitBounds(L.polygon(g.g).getBounds().pad(0.3));
  });
  $('panel').querySelectorAll('a[data-dam]').forEach(e => e.onclick = ev => { ev.preventDefault(); select(e.dataset.dam, true) });
  panelTime();
}
// ส่วนที่เปลี่ยนตามตัวเลื่อนเวลา: ค่า ณ วันที่เลือก, กราฟ, รายการธงต้นน้ำ/ท้ายน้ำ
function flagList(list, max) {
  const ev = list.map(f => [f, flagAt(f)]).filter(x => x[1].sev != null)
    .sort((a, b) => b[1].sev - a[1].sev || (b[1].pct || 0) - (a[1].pct || 0));
  const red = ev.filter(x => x[1].sev === 2).length, yel = ev.filter(x => x[1].sev === 1).length;
  let h = '<div class="mut">' + ev.length + ' สถานีมีข้อมูล · แดง ' + red + ' · เหลือง ' + yel + (off > 0 ? ' (ค่าล่าสุด)' : '') + '</div>';
  h += ev.filter(x => x[1].sev >= 1).slice(0, max).map(([f, a]) => '<div class="flagrow" data-fl="' + D.flags.indexOf(f) + '"><span>' +
    flagSvg(FLAGC[a.sev], 14) + ' ' + f.name + ' <span class="mut">' + f.river + ' · ' + f.pro + '</span>' + (f.suspect ? ' ⚠' : '') +
    '</span><b>' + (a.pct != null ? f0(a.pct) + '%' : '') + '</b></div>').join('');
  if (red + yel > max) h += '<div class="mut">และอีก ' + (red + yel - max) + ' สถานี</div>';
  return h;
}
function bindFlagRows(root) {
  root.querySelectorAll('[data-fl]').forEach(e => e.onclick = () => { const f = D.flags[+e.dataset.fl]; map.setView([f.lat, f.lon], 11) });
}
function panelTime() {
  if (mode === 'area') return showArea();
  if (mode === 'basin') return showBasin(false);
  const d = D.dams.find(x => x.name === selName); if (!d) return;
  const a = damAt(d), el = $('tnow');
  if (el) el.innerHTML = '<b>' + thd(curDate()) + '</b> ' + (a.kind === 'fc' ? '<span class="badge kind-fc">คาดการเชิงสถิติ</span>' : '<span class="badge kind-obs">ข้อมูลจริง</span>') +
    '<div style="font-size:1.3rem;font-weight:700;margin-top:2px">' + (a.p == null ? 'ไม่มีข้อมูล' : f1(a.p) + '%') +
    (a.kind === 'fc' && a.p != null ? ' <span style="font-size:.85rem;font-weight:400" class="sub">ช่วงคาด ' + f1(a.lo) + '-' + f1(a.hi) + '%</span>' : '') + '</div>' +
    (a.kind === 'fc' && a.p > 100 ? '<div class="sub" style="font-size:.82rem">⚠ ถ้าแนวโน้มนี้ต่อเนื่อง อ่างจะเกินระดับเก็บกักปกติ ' +
      'หน่วยงานมักต้องเร่งระบาย → พื้นที่ท้ายน้ำ (สีน้ำเงินบนแผนที่) จะรับน้ำเพิ่ม · ค่าคาดการไม่รวมแผนระบายจริง</div>' : '');
  const zc = [...zoneCodes], dn = D.flags.filter(f => f.geo && zoneCodes.has(f.geo));
  const zf = $('zflags'); if (zf) zf.innerHTML = flagList(dn, 12);
  const uf = $('upflags');
  if (uf) uf.innerHTML = '<div class="sec" style="font-size:.85rem">ธงภัยต้นน้ำ</div>' +
    flagList(D.flags.filter(f => f.geo && upCodes.has(f.geo) && !zoneCodes.has(f.geo)), 8);
  bindFlagRows($('panel'));
  drawChart(d);
}
window.clearSel = () => { selName = null; mode = 'overview'; resetLayers(); renderFlags(); showOverview() };

// ---------- โหมดลุ่มเจ้าพระยาทั้งระบบ: ต้นน้ำภาคเหนือ → เขื่อน → เจ้าพระยา → กทม. ----------
function showBasin(fit) {
  const B = D.basin; if (!B) return;
  const dams = D.dams.filter(d => B.dams.includes(d.name));
  if (fit) {
    resetLayers(); selName = null; mode = 'basin';
    if (area !== 'all') { area = 'all'; $('area').value = 'all' }
    $('bBasin').classList.add('on');
    upCodes = new Set(B.codes); dimOthers = new Set(B.dams);
    drawUp(B.chains, B.area_km2);
    drawFlows(dams.filter(d => d.name === 'ป่าสักชลสิทธิ์'));   // เส้นผันเข้าคลองระพีพัฒน์ถึง กทม. ฝั่งตะวันออก
    const b = L.latLngBounds(B.chains.flatMap(c => c.g)); map.fitBounds(b.pad(0.02));
    refreshDams(); renderFlags();
  }
  // ตารางจังหวัดเรียงเหนือ → ใต้ ณ วันที่เลือก
  const fl = D.flags.filter(f => (f.geo && B.codes.includes(f.geo)) || BKK.includes(f.pro));
  const prov = {};
  fl.forEach(f => { const a = flagAt(f); if (a.sev == null) return;
    const p = prov[f.pro] = prov[f.pro] || {n: 0, r: 0, y: 0, lat: 0}; p.n++; p.lat += f.lat; if (a.sev === 2) p.r++; if (a.sev === 1) p.y++ });
  const rows = Object.entries(prov).map(([k, v]) => [k, v, v.lat / v.n]).sort((a, b) => b[2] - a[2]);
  let h = '<h2>ลุ่มเจ้าพระยา เหนือ → กทม.</h2><div class="sub" style="font-size:.85rem">พื้นที่รับน้ำ ~' + f0(B.area_km2) +
    ' km² · เส้นฟ้า = ลำน้ำทั้งลุ่มไหลลงใต้ (HydroRIVERS) · เส้นน้ำเงินเข้ม = ป่าสักผันเข้าคลองระพีพัฒน์ถึงฝั่งตะวันออก กทม.</div>' +
    '<div class="sec">เขื่อนในลุ่ม ณ ' + thd(curDate()) + '</div>' +
    dams.sort((a, b) => b.lat - a.lat).map(d => { const a = damAt(d), s = statusP(a.p, d);
      return '<div data-dam="' + d.name + '" style="cursor:pointer;display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px solid var(--line);font-size:.86rem">' +
        '<span><span class="dot" style="background:' + s.c + '"></span> ' + d.name + ' <span class="mut">' + d.province + '</span></span><b>' +
        (a.p == null ? '–' : f1(a.p) + '%') + (a.kind === 'fc' ? '*' : '') + '</b></div>' }).join('') +
    (off > 0 ? '<div class="mut">* คาดการเชิงสถิติ</div>' : '') +
    '<div class="sec">ธงภัยรายจังหวัด เรียงจากเหนือลงใต้</div><table class="prov"><tr><th>จังหวัด</th><th>สถานี</th><th>แดง</th><th>เหลือง</th></tr>' +
    rows.map(([k, v]) => '<tr><td>' + k + '</td><td>' + v.n + '</td><td>' + (v.r ? '<b style="color:var(--crit)">' + v.r + '</b>' : 0) +
      '</td><td>' + (v.y ? '<b>' + v.y + '</b>' : 0) + '</td></tr>').join('') + '</table>' +
    (off > 0 ? '<div class="mut">วันในอนาคต: ธงเป็นค่าล่าสุด (ไม่มีพยากรณ์รายสถานี)</div>' : '');
  $('panel').innerHTML = h;
  $('panel').querySelectorAll('[data-dam]').forEach(e => e.onclick = () => select(e.dataset.dam, true));
}
$('bBasin').onclick = () => showBasin(true);

// ---------- โหมดพื้นที่: ธงทุกสีในพื้นที่ที่เลือก ----------
function showArea(fit) {
  const fl = D.flags.filter(inArea);
  if (fit) {
    const pts = fl.map(f => [f.lat, f.lon]);
    if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15));
  }
  $('panel').innerHTML = '<h2>ธงภัย: ' + AREAS[area].t + '</h2><div class="mut">' + thd(curDate()) +
    (off > 0 ? ' · ค่าล่าสุด (ไม่มีพยากรณ์รายสถานี)' : '') + '</div>' + flagList(fl, 40);
  bindFlagRows($('panel'));
}
$('area').onchange = () => {
  area = $('area').value;
  if (area === 'all') { mode = 'overview'; renderFlags(); showOverview(); map.setView([13.4, 101.0], 6); return }
  resetLayers(); selName = null; mode = 'area';
  renderFlags(); showArea(true);
};

// ---------- ตัวเลื่อนเวลา ----------
const tr = $('tRange');
tr.min = MINOFF; tr.max = MAXOFF; tr.step = 1; tr.value = 0;
const pos = o => (o - MINOFF) / (MAXOFF - MINOFF) * 100;
tr.style.background = 'linear-gradient(to right, transparent 0%, transparent 100%)';
$('tScale').innerHTML = [[MINOFF, MINOFF + ' วัน'], [Math.round(MINOFF / 2), Math.round(MINOFF / 2) + ' วัน'], [0, 'วันนี้'], [MAXOFF, '+' + MAXOFF]]
  .map(([o, t], i, arr) => '<span style="left:' + pos(o) + '%;' + (i === 0 ? 'transform:none' : i === arr.length - 1 ? 'transform:translateX(-100%)' : '') + '">' + t + '</span>').join('');
function updateTime() {
  tr.value = off;
  const dt = curDate();
  $('tDate').textContent = thd(dt) + (off === 0 ? ' (วันนี้)' : off < 0 ? ' (' + off + ' วัน)' : ' (+' + off + ' วัน)');
  const k = $('tKind');
  k.className = 'badge ' + (off > 0 ? 'kind-fc' : 'kind-obs');
  k.textContent = off > 0 ? 'คาดการเชิงสถิติ' : 'ข้อมูลจริง';
  const fOk = off <= 0 && (off === 0 || FIDX[dt] != null);
  $('tNote').textContent = off > 0 ? 'เขื่อน = คาดการ % ความจุ · ธงภัย = ค่าล่าสุดแบบจาง (ไม่มีพยากรณ์รายสถานี)' :
    (fOk ? '' : 'ยังไม่มีประวัติธงภัยของวันนี้ (มีตั้งแต่ ' + (D.fdates[0] ? thd(D.fdates[0]) : '–') + ')');
  $('mapdate').innerHTML = '<b>' + thd(dt) + '</b> · ' + (off > 0 ? 'คาดการ' : 'ข้อมูลจริง');
  refreshDams(); renderFlags();
  if (mode === 'dam' || mode === 'basin' || mode === 'area') panelTime();
}
let playT = null;
function stopPlay() { clearInterval(playT); playT = null; $('tPlay').textContent = '▶ เล่น' }
tr.oninput = () => { off = +tr.value; updateTime() };
$('tPrev').onclick = () => { stopPlay(); off = Math.max(MINOFF, off - 1); updateTime() };
$('tNext').onclick = () => { stopPlay(); off = Math.min(MAXOFF, off + 1); updateTime() };
$('tToday').onclick = () => { stopPlay(); off = 0; updateTime() };
$('tPlay').onclick = () => {
  if (playT) return stopPlay();
  if (off >= MAXOFF) off = Math.max(MINOFF, -60);
  $('tPlay').textContent = '⏸ หยุด';
  playT = setInterval(() => { if (off >= MAXOFF) return stopPlay(); off++; updateTime() }, 300);
};
$('btNote').textContent = 'ทดสอบย้อนหลัง ' + D.bt['7'].n + ' ครั้ง ความคลาดเคลื่อนเฉลี่ย: 7 วัน ' + D.bt['7'].model +
  ' จุด% (ค่าคงที่ ' + D.bt['7'].persistence + ') · 14 วัน ' + D.bt['14'].model + ' (' + D.bt['14'].persistence + ') · 30 วัน ' +
  D.bt['30'].model + ' (' + D.bt['30'].persistence + ')';

// ---------- chart: แกนเดียว (%) · จริง = เส้นทึบ · คาดการ = เส้นประ + แถบ · ปีที่แล้ว = ประเทา ----------
function drawChart(d) {
  const el = $('chart'); if (!el) return;
  const a = d.hist, b = d.hist_ly, fc = d.fc || [];
  if (!a.length) { el.innerHTML = '<div class="mut">ไม่มีประวัติรายวันจาก RID สำหรับเขื่อนนี้</div>'; return }
  const W = 420, Hh = 180, L0 = 34, R0 = 8, T0p = 8, B0 = 22;
  const x0 = UT(a[0][0]), x1 = fc.length ? UT(fc[fc.length - 1][0]) : UT(a[a.length - 1][0]);
  const vals = a.map(p => p[1]).concat(b.filter(p => UT(p[0]) <= x1).map(p => p[1]), fc.flatMap(p => [p[2], p[3]]), [100, d.urc_pct || 0]);
  const mn = Math.min(...vals), mx = Math.max(...vals), step = mx - mn > 40 ? 20 : 10;
  const lo = Math.max(0, Math.floor(mn / step) * step), hi = Math.ceil(mx / step) * step;
  const X = t => L0 + (UT(t) - x0) / (x1 - x0 || 1) * (W - L0 - R0), Y = v => T0p + (hi - v) / (hi - lo) * (Hh - T0p - B0);
  const path = (s, k = 1) => s.filter(p => UT(p[0]) >= x0 && UT(p[0]) <= x1).map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[k]).toFixed(1)).join('');
  let g = '';
  for (let v = lo; v <= hi; v += step) g += '<line x1="' + L0 + '" x2="' + (W - R0) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="var(--line)"/>' +
    '<text x="' + (L0 - 4) + '" y="' + (Y(v) + 4) + '" text-anchor="end" font-size="10" fill="var(--mut)">' + v + '</text>';
  a.concat(fc).forEach(p => { if (p[0].slice(8) === '01') g += '<text x="' + X(p[0]) + '" y="' + (Hh - 6) + '" font-size="10" fill="var(--mut)" text-anchor="middle">' + THM[+p[0].slice(5, 7) - 1] + '</text>' });
  if (fc.length) {   // พื้นหลังช่วงคาดการ
    g += '<rect x="' + X(D.today) + '" y="' + T0p + '" width="' + (X(fc[fc.length - 1][0]) - X(D.today)) + '" height="' + (Hh - T0p - B0) + '" fill="var(--t3)" opacity=".12"/>';
    const band = fc.map(p => X(p[0]).toFixed(1) + ' ' + Y(p[3]).toFixed(1)).concat(fc.slice().reverse().map(p => X(p[0]).toFixed(1) + ' ' + Y(p[2]).toFixed(1)));
    g += '<path d="M' + X(D.today) + ' ' + Y(d.pct) + 'L' + band.join('L') + 'Z" fill="var(--t3)" opacity=".45"/>';
    g += '<path d="M' + X(D.today) + ' ' + Y(d.pct) + path(fc).replace(/^M/, 'L') + '" fill="none" stroke="var(--t2)" stroke-width="2" stroke-dasharray="5 3"/>';
  }
  if (hi >= 100) g += '<line x1="' + L0 + '" x2="' + (W - R0) + '" y1="' + Y(100) + '" y2="' + Y(100) + '" stroke="var(--crit)" stroke-dasharray="4 3"/>';
  g += '<path d="' + path(b) + '" fill="none" stroke="var(--ly)" stroke-width="2" stroke-dasharray="4 3"/>';
  g += '<path d="' + path(a) + '" fill="none" stroke="var(--t1)" stroke-width="2"/>';
  const last = a[a.length - 1];
  g += '<circle cx="' + X(last[0]) + '" cy="' + Y(last[1]) + '" r="4" fill="var(--t1)" stroke="var(--card)" stroke-width="2"/>';
  if (d.urc_pct != null) { const ux = X(last[0]), uy = Y(d.urc_pct);
    g += '<path d="M' + ux + ' ' + (uy - 5) + 'L' + (ux + 5) + ' ' + uy + 'L' + ux + ' ' + (uy + 5) + 'L' + (ux - 5) + ' ' + uy + 'Z" fill="var(--serious)" stroke="var(--card)" stroke-width="1.5"/>' }
  const sx = X(curDate());   // วันที่เลือกจากตัวเลื่อน
  g += '<line x1="' + sx + '" x2="' + sx + '" y1="' + T0p + '" y2="' + (Hh - B0) + '" stroke="var(--ink)" stroke-width="1.5"/>';
  const sa = damAt(d);
  if (sa.p != null) g += '<circle cx="' + sx + '" cy="' + Y(sa.p) + '" r="4.5" fill="var(--card)" stroke="var(--ink)" stroke-width="2"/>';
  g += '<line id="cx" y1="' + T0p + '" y2="' + (Hh - B0) + '" stroke="var(--mut)" visibility="hidden"/>';
  g += '<rect x="' + L0 + '" y="0" width="' + (W - L0 - R0) + '" height="' + Hh + '" fill="transparent" id="hit" style="cursor:pointer"/>';
  el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + Hh + '">' + g + '</svg>';
  const bm = {}; b.forEach(p => bm[p[0]] = p[1]);
  const pts = a.map(p => [p[0], p[1], null]).concat(fc.map(p => [p[0], p[1], p]));
  const svg = el.querySelector('svg'), tip = $('tip'), cx = el.querySelector('#cx');
  const nearest = e => { const r = svg.getBoundingClientRect(), px = (e.clientX - r.left) / r.width * W;
    return pts.reduce((best, p) => Math.abs(X(p[0]) - px) < Math.abs(X(best[0]) - px) ? p : best, pts[0]) };
  el.querySelector('#hit').addEventListener('mousemove', e => {
    const p = nearest(e);
    cx.setAttribute('x1', X(p[0])); cx.setAttribute('x2', X(p[0])); cx.setAttribute('visibility', 'visible');
    tip.innerHTML = thd(p[0]) + '<br><b>' + f1(p[1]) + '%</b>' + (p[2] ? ' คาดการ (ช่วง ' + f1(p[2][2]) + '-' + f1(p[2][3]) + ')' : '') +
      (bm[p[0]] != null ? '<br>ปีที่แล้ว ' + f1(bm[p[0]]) + '%' : '') + '<br><span style="color:#888">กดเพื่อเลื่อนแผนที่ไปวันนี้</span>';
    tip.style.display = 'block'; tip.style.left = (e.pageX + 12) + 'px'; tip.style.top = (e.pageY - 10) + 'px';
  });
  el.querySelector('#hit').addEventListener('mouseleave', () => { tip.style.display = 'none'; cx.setAttribute('visibility', 'hidden') });
  el.querySelector('#hit').addEventListener('click', e => { stopPlay(); off = Math.round((UT(nearest(e)[0]) - T0) / DAY); tip.style.display = 'none'; updateTime() });
}

// ---------- table ----------
const COLS = [
  ['name', 'เขื่อน'], ['province', 'จังหวัด'], ['pct', '% ความจุ'], ['d7', 'Δ 7 วัน'], ['ly', 'ปีที่แล้ว'],
  ['volume', 'ปริมาตร'], ['room', 'รับน้ำได้อีก'], ['inflow', 'ไหลเข้า/วัน'], ['outflow', 'ระบาย/วัน'], ['verdict', 'ข้อมูล']];
let sortKey = 'region', sortDir = -1;
function renderTable() {
  let h = '<tr>' + COLS.map(c => '<th data-k="' + c[0] + '">' + c[1] + (sortKey === c[0] ? (sortDir > 0 ? ' ▲' : ' ▼') : '') + '</th>').join('') + '</tr>';
  let rows = D.dams.slice();
  const byRegion = sortKey === 'region';
  if (byRegion) rows.sort((a, b) => (a.region || 'ฮ').localeCompare(b.region || 'ฮ', 'th') || (b.pct || 0) - (a.pct || 0));
  else rows.sort((a, b) => { const x = a[sortKey], y = b[sortKey];
    if (x == null) return 1; if (y == null) return -1;
    return (typeof x === 'string' ? x.localeCompare(y, 'th') : x - y) * sortDir });
  let grp = null;
  rows.forEach(d => {
    if (byRegion && d.region !== grp) { grp = d.region; h += '<tr class="grp"><td colspan="' + COLS.length + '">' + (grp || 'เขื่อน กฟผ. (นอกรายการ RID)') + '</td></tr>' }
    const s = status(d);
    const bar = d.pct == null || d.run_of_river ? 'ฝายน้ำล้น' :
      '<span class="bar"><i style="width:' + Math.min(100, d.pct / 1.2) + '%;background:' + s.c + '"></i><u style="left:' + (100 / 1.2) + '%"></u></span>' + f1(d.pct);
    h += '<tr class="row' + (d.name === selName ? ' selrow' : '') + '" data-dam="' + d.name + '"><td><b>' + d.name + '</b></td><td>' + d.province + '</td>' +
      '<td>' + bar + '</td><td>' + (d.d7 == null ? '–' : (d.d7 >= 0 ? '+' : '') + f1(d.d7)) + '</td><td>' + f1(d.ly) + '</td>' +
      '<td>' + f0(d.volume) + '</td><td>' + (d.room == null ? '–' : d.room < 0 ? 'เกิน ' + f0(-d.room) : f0(d.room)) + '</td>' +
      '<td>' + f2(d.inflow) + '</td><td>' + f2(d.outflow) + '</td>' +
      '<td>' + (d.verdict === 'agree' ? '✓ ' + Object.keys(d.sources).join('+') : d.verdict === 'differ' ? '⚠ ไม่ตรง' : d.primary) + '</td></tr>';
  });
  $('tbl').innerHTML = h;
  $('tbl').querySelectorAll('th').forEach(th => th.onclick = () => {
    const k = th.dataset.k;
    if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = typeof D.dams[0][k] === 'string' ? 1 : -1 }
    renderTable();
  });
  $('tbl').querySelectorAll('tr.row').forEach(r => r.onclick = () => {
    select(r.dataset.dam, true); document.getElementById('map').scrollIntoView({behavior: 'smooth', block: 'start'});
  });
}
renderTable();
showOverview();
updateTime();
</script>
</body></html>
"""

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
out = os.path.join(BASE, "dashboard.html")
open(out, "w").write(html)
print("OK", out, f"| dams={len(dams)} districts={len(geo_used)} size={len(html.encode())/1e6:.2f} MB")
