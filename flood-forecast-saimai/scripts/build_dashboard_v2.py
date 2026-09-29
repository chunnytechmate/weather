#!/usr/bin/env python3
"""ประกอบ dashboard v2: timeline ย้อนหลัง 60 วัน + คาดการ 90 วัน เลือกวันได้
   เน้นเข้าใจง่าย: ไฟจราจรคำนวณตามวันที่เลือก + แผงตัวแปรโมเดล + ป้าย 'การคาดการเชิงสถิติ'
   เขียน dashboard-saimai.html (หน้าหลัก dashboard.html เป็นเขื่อนทั่วประเทศ, v1 สำรองไว้ที่ dashboard-v1.html)"""
import json, glob, os, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def latest(path):
    fs = sorted(glob.glob(os.path.join(BASE, "data", path)))
    return json.load(open(fs[-1])) if fs else {}

sn = latest("snapshots/snapshot-*.json")
fc = json.load(open(os.path.join(BASE, "data", "fc_days.json")))
hist = json.load(open(os.path.join(BASE, "data", "station_history.json")))
if not sn:
    raise SystemExit("ไม่มี snapshot")

hist_st = hist.get("stations", {})
hist_can = hist.get("canals", {})
st_by_key = {s.get("key"): s for s in sn.get("stations", [])}

def match_hist(key, name):
    """หาประวัติของสถานี โดย key ของ fc อาจสั้นกว่า key ของ history (เช่น นวลฉวี vs สะพานนวลฉวี)"""
    if key in hist_st:
        return hist_st[key]
    for hk, hv in hist_st.items():
        if key in hk or hk in name:
            return hv
    for hk, hv in hist_can.items():
        if key in hk or hk in name:
            return hv
    return None

# ---- สถานีที่มี forecast (หลัก) + ประวัติ ----
stations = []
for st in fc.get("stations", []):
    h = match_hist(st["key"], st["name"])
    stations.append({
        "key": st["key"], "name": st["name"], "grp": st["grp"],
        "normal": st.get("normal"), "ref": st.get("ref"), "warn": st.get("warn"),
        "msl_now": (st_by_key.get(st["key"]) or {}).get("msl"),
        "hist": (h or {}).get("daily", []),
        "fc": [[v["d"], v["h"], v["lo"], v["hi"], v["tier"]] for v in st["series"]],
    })

# ---- สถานีที่มีแค่ประวัติ (สายน้ำเต็ม) ให้เลือกดูได้เพิ่ม ----
# ข้ามที่ซ้ำกับสถานี fc (key ของ fc อาจสั้นกว่า เช่น นวลฉวี vs สะพานนวลฉวี)
fc_sts = [s for s in stations if s["fc"]]
for hk, hv in hist_st.items():
    if any(s["key"] == hk or s["key"] in hk for s in fc_sts):
        continue
    grp = (st_by_key.get(hk) or {}).get("group", "")
    stations.append({"key": hk, "name": hv.get("name", hk), "grp": grp,
                     "normal": hv.get("normal"), "ref": None, "warn": None,
                     "msl_now": (st_by_key.get(hk) or {}).get("msl"),
                     "hist": hv.get("daily", []), "fc": []})

# ---- ฝน: ซอย + เหนือ (เฉลี่ย 4 จุด) รายวัน ----
wd = sn.get("wx_daily", {})
rain_soi = [[t, p] for t, p in zip(wd.get("time", []), wd.get("precipitation_sum", [])) if p is not None]
nsum, ncnt = {}, {}
for w in sn.get("wx_north", []):
    for t, p in zip(w.get("time", []), w.get("precip", [])):
        if p is None:
            continue
        nsum[t] = nsum.get(t, 0.0) + float(p)
        ncnt[t] = ncnt.get(t, 0) + 1
rain_north = [[t, round(nsum[t] / ncnt[t], 1)] for t in sorted(nsum)]

# ---- เขื่อน ----
dams = [{"name": d["name"], "pct": d.get("storage_pct"), "inflow": d.get("inflow"),
         "released": d.get("released_daily")} for d in sn.get("dams", [])]
dams_top = [{"name": d["name"], "pct": d.get("storage_pct"), "basin": d.get("basin", "")}
            for d in sorted(sn.get("dams_all", []), key=lambda x: -x.get("storage_pct", 0))[:8]]

# ---- ไฟจราจรเกณฑ์ (ให้ JS คำนวณตามวันที่เลือก) ----
klong2 = next((c for c in sn.get("canals", []) if "คลองสอง" in c.get("name", "")), None)
canal_k2 = {"warn": klong2 and klong2.get("warn"), "crit": klong2 and klong2.get("crit"),
            "value": klong2 and klong2.get("value")}

DATA = {
    "built_at": sn["fetched_at"], "fc_built_at": fc.get("built_at"),
    "hist_built_at": hist.get("built_at"),
    "today": sn["fetched_at"][:10],
    "nwp_days": fc.get("nwp_days", 16), "seasonal_trust": fc.get("seasonal_trust", 35),
    "horizon": fc.get("horizon", 90), "dam_release_mcm": fc.get("dam_release_mcm"),
    "v_bpa": fc.get("v_bpa"), "dam_inflow_mcm": fc.get("dam_inflow_mcm"),
    "bpa_excess": fc.get("bpa_excess"),
    "stations": stations, "rain_soi": rain_soi, "rain_north": rain_north,
    "dams": dams, "dams_top": dams_top, "canal_k2": canal_k2,
    "canals": sn.get("canals", []), "roads": sn.get("roads", []),
}

HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>น้ำท้ายซอยสายไหม 44: ย้อนหลัง 60 วัน คาดการ 90 วัน</title>
<style>
:root{--ink:#1e293b;--sub:#64748b;--line:#e2e8f0;--teal:#0d9488;--orange:#ea580c;
--blue:#2563eb;--red:#dc2626;--amber:#b45309;--amberbg:#fffbeb;--green:#16a34a}
*{box-sizing:border-box}
body{font-family:-apple-system,"Sarabun","Noto Sans Thai","Segoe UI",sans-serif;
margin:0;background:#f8fafc;color:var(--ink);line-height:1.55}
.wrap{max-width:980px;margin:0 auto;padding:14px 14px 60px}
h1{font-size:1.35rem;margin:.2em 0 .1em}
h2{font-size:1.05rem;margin:1.6em 0 .5em;color:var(--ink)}
.mut{color:var(--sub);font-size:.85rem}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0}
.warn{background:var(--amberbg);border:1px solid #fcd34d;border-radius:12px;padding:10px 14px;margin:10px 0;font-size:.9rem}
.warn b{color:var(--amber)}
/* scrubber */
.datedisp{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:6px 0}
.datedisp .big{font-size:1.5rem;font-weight:700}
.tierchip{font-size:.75rem;padding:2px 8px;border-radius:999px;border:1px solid}
.t1{background:#ecfdf5;border-color:#a7f3d0;color:#047857}
.t2{background:#fffbeb;border-color:#fde68a;color:#b45309}
.t3{background:#f1f5f9;border-color:#cbd5e1;color:#475569}
.t0{background:#fff;border-color:var(--line);color:var(--sub)}
input[type=range]{width:100%;height:34px}
.qbtns{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0}
.qbtns button{font:inherit;font-size:.85rem;padding:4px 12px;border-radius:8px;border:1px solid var(--line);
background:#fff;cursor:pointer}
.qbtns button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
/* lights */
.lights{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px}
.light{display:flex;gap:10px;align-items:flex-start;background:#fff;border:1px solid var(--line);
border-radius:10px;padding:8px 10px}
.dot{width:16px;height:16px;border-radius:50%;flex:none;margin-top:4px}
.g{background:var(--green)}.y{background:#d97706}.r{background:var(--red)}.x{background:#cbd5e1}
.light .t{font-weight:600;font-size:.9rem}
.light .v{font-size:.85rem;color:var(--sub)}
.verdict{font-size:1.05rem;font-weight:700;padding:10px 14px;border-radius:10px;margin:10px 0}
/* chart */
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.chips button{font:inherit;font-size:.82rem;padding:3px 10px;border-radius:999px;border:1px solid var(--line);
background:#fff;cursor:pointer}
.chips button.on{background:var(--teal);color:#fff;border-color:var(--teal)}
svg{display:block;width:100%;height:auto}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.8rem;color:var(--sub);margin-top:4px}
.legend i{display:inline-block;width:18px;height:3px;border-radius:2px;margin-right:4px;vertical-align:middle}
/* table */
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
.pill{display:inline-block;font-size:.72rem;padding:1px 8px;border-radius:999px}
.ok{background:#ecfdf5;color:#047857}.hi{background:#fff7ed;color:#c2410c}.crit{background:#fef2f2;color:#b91c1c}
/* variables */
.vars{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:8px}
.var{background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.var .n{font-weight:600;font-size:.88rem}
.var .val{font-size:.85rem;color:var(--orange);font-weight:600}
.var .d{font-size:.8rem;color:var(--sub)}
.src{font-size:.7rem;color:#94a3b8}
/* dams */
.dam{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:.85rem}
.bar{flex:1;height:10px;background:#f1f5f9;border-radius:6px;overflow:hidden}
.bar i{display:block;height:100%}
.bar i.ok{background:var(--green)}
.bar i.warm{background:#d97706}
.bar i.hot{background:var(--red)}
a{color:var(--blue)}
@media(max-width:640px){td,th{padding:5px 5px;font-size:.8rem}}
</style>
</head>
<body><div class="wrap">

<h1>น้ำท้ายซอยสายไหม 44</h1>
<div class="mut">ข้อมูลจริง: thaiwater (กรมชลประทาน/HII) + Open-Meteo · อัปเดตล่าสุด <span id="built"></span> ·
อัปเดตอัตโนมัติทุกชั่วโมง (refresh หน้านี้)</div>

<div class="warn"><b>อ่านก่อน:</b> เส้นส้มทั้งหมดคือ <b>การคาดการเชิงสถิติ</b> จากโมเดล lag-route
ที่พารามิเตอร์ตั้งมือ ยังไม่ได้ calibrate กับเหตุการณ์จริง ไม่ใช่พยากรณ์ทางการ
วันที่ 1-16 ใช้ฝนพยากรณ์ (NWP) อ่านได้ระดับหนึ่ง · วันที่ 17-35 เป็นสถานการณ์คาดหมายจาก SEAS5 ·
วันที่ 36-90 เป็นแนวโน้มตามสถิติฤดูกาล ความแม่นต่ำ อ่านเป็น "แนวโน้มระดับน้ำ" เท่านั้น
ตัดสินใจสำคัญให้ดูประกาศหน่วยงานทางการ (กรมชลประทาน / กทม. / TMD)</div>

<h2>เลือกวันที่ดู</h2>
<div class="card">
  <div class="datedisp"><span class="big" id="dsel"></span><span class="mut" id="dnote"></span>
  <span class="tierchip t0" id="dtier"></span></div>
  <input type="range" id="scrub" min="0" max="1" value="0">
  <div class="qbtns">
    <button data-q="-60">60 วันก่อน</button><button data-q="-30">30 วันก่อน</button>
    <button data-q="-7">7 วันก่อน</button><button data-q="0" class="on">วันนี้</button>
    <button data-q="7">+7 วัน</button><button data-q="30">+30 วัน</button>
    <button data-q="90">+90 วัน</button>
  </div>
</div>

<h2>ไฟจราจร 7 ดวง ของวันที่เลือก</h2>
<div class="lights" id="lights"></div>
<div class="verdict" id="verdict"></div>

<h2>กราฟระดับน้ำรายสถานี (ย้อนหลัง 60 วัน + คาดการ 90 วัน)</h2>
<div class="card">
  <div class="chips" id="stchips"></div>
  <div id="chart"></div>
  <div class="legend">
    <span><i style="background:var(--teal)"></i>ข้อมูลจริง (ย้อนหลัง)</span>
    <span><i style="background:var(--orange)"></i>คาดการเชิงสถิติ (แถบ = ช่วงคาด lo-hi)</span>
    <span><i style="background:var(--blue)"></i>ระดับปกติ</span>
    <span><i style="background:var(--red)"></i>เกณฑ์</span>
    <span><i style="background:#94a3b8;height:14px;width:3px"></i>วันนี้ / เส้นแบ่ง tier</span>
  </div>
  <div class="mut" style="margin-top:6px">ฝนที่ซอยรายวัน (แท่งเทา = ตกจริง, แท่งส้ม = ฝนคาดการ NWP)</div>
  <div id="rain"></div>
</div>

<h2>ค่ารายสถานี วันที่เลือก</h2>
<div class="card" style="overflow-x:auto"><table id="tbl"></table></div>

<h2>ตัวแปรที่โมเดลใช้คำนวณ (ทั้งหมดเป็นสถิติ/ประจักษ์ ไม่มีข้อมูลลับ)</h2>
<div class="vars" id="vars"></div>
<div class="mut" id="fcnote" style="margin-top:8px"></div>

<h2>เขื่อน</h2>
<div class="card">
  <div style="font-weight:600;font-size:.9rem">เขื่อนต้นน้ำเจ้าพระยา (ผูกกับระดับน้ำฝั่งเราโดยตรง)</div>
  <div id="damskey"></div>
  <div style="font-weight:600;font-size:.9rem;margin-top:10px">ทั่วประเทศ 8 อันดับ % ความจุสูงสุด (มีครบ 39 แห่งใน snapshot)</div>
  <div id="damstop"></div>
</div>

<h2>เซ็นเซอร์ใกล้ซอย (วันนี้)</h2>
<div class="card" id="near"></div>

<div class="mut" style="margin-top:24px">
แหล่งข้อมูล: ระดับน้ำ = api-v3.thaiwater.net · ฝน/พยากรณ์ = Open-Meteo (NWP + ECMWF SEAS5) ·
โมเดลและวิธีอ่าน: <code>docs/FORECAST.md</code> ใน repository ·
เขื่อนทั่วประเทศ + แผนที่พื้นที่ท้ายน้ำ: <a href="dashboard.html">dashboard.html</a> ·
dashboard แบบเก่า: <a href="dashboard-v1.html">dashboard-v1.html</a><br>
สร้างโดย cron ทุกชั่วโมง: fetch_snapshot.py &rarr; forecast_days.py &rarr; build_dashboard_v2.py
</div>

</div>
<script>
const D = __DATA__;
const THD=['อาทิตย์','จันทร์','อังคาร','พุธ','พฤหัส','ศุกร์','เสาร์'];
const THM=['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
// ---- คณิตวันที่แบบ UTC ล้วน (กัน bug เลื่อนวันจาก timezone) ----
const U=d=>{const[y,m,dd]=d.split('-').map(Number);return Date.UTC(y,m-1,dd)};
const addD=(d,n)=>{const t=new Date(U(d)+n*864e5);return t.toISOString().slice(0,10)};
const dOff=d=>Math.round((U(d)-U(D.histStart))/864e5);
const dAt=i=>addD(D.histStart,i);
const fmtD=d=>{const x=new Date(U(d));return 'วัน'+THD[x.getUTCDay()]+' '+x.getUTCDate()+' '+THM[x.getUTCMonth()]+' '+(x.getUTCFullYear()+543)};
function jd2(d){return U(d)/864e5+2440587.5}
function tideMult(d){const ph=((jd2(d)-2451550.26)/29.530588853);const f=ph-Math.floor(ph);
const s=(1+Math.cos(4*Math.PI*f))/2;return 1-0.55*s}

// ---- day array ----
const todayIdx=dOff(D.today), nAll=dOff(D.fcEnd)+1;
let sel=todayIdx;
function selDate(){return dAt(sel)}

// ---- per-station lookup maps ----
D.stations.forEach(s=>{s.hmap={};s.hist.forEach(p=>s.hmap[p[0]]=p[1]);
s.fmap={};s.fc.forEach(p=>s.fmap[p[0]]=p);});
const byKey=k=>D.stations.find(s=>s.key===k);
function valAt(s,d){if(s.hmap[d]!==undefined)return{v:s.hmap[d],src:'h'};
if(s.fmap[d])return{v:s.fmap[d][1],lo:s.fmap[d][2],hi:s.fmap[d][3],tier:s.fmap[d][4],src:'f'};return null}
const rainSoi={},rainNorth={};D.rain_soi.forEach(p=>rainSoi[p[0]]=p[1]);D.rain_north.forEach(p=>rainNorth[p[0]]=p[1]);

// ---- scrubber ----
const scrub=document.getElementById('scrub');
scrub.min=0;scrub.max=nAll-1;scrub.value=sel;
scrub.oninput=()=>{sel=+scrub.value;render()};
document.querySelectorAll('.qbtns button').forEach(b=>b.onclick=()=>{
let i=Math.min(nAll-1,Math.max(0,todayIdx+ +b.dataset.q));scrub.value=i;sel=i;render()});

function tierOf(i){if(i<=todayIdx)return 0;const f=i-todayIdx;
if(f<=D.nwp_days)return 1;if(f<=D.seasonal_trust)return 2;return 3}
const tierName=['ข้อมูลจริง','tier 1: ฝน NWP','tier 2: SEAS5 คาดหมาย','tier 3: สถิติฤดูกาล'];

// ---- lights ----
function lights(){
const d=selDate(),prev=addD(d,-1);
const L=[];
const lv=(v,g,y)=>v==null?'x':(v<=g?'g':(v<=y?'y':'r'));
const r=rainSoi[d];L.push({c:lv(r==null?null:r,5,20),t:'ฝนที่ซอย วันนั้น',
v:r==null?'ไม่มีข้อมูล':r.toFixed(1)+' มม.',rule:'เขียว ≤5 / เหลือง ≤20 / แดง >20 มม.'});
const nul=valAt(byKey('นวลฉวี')||{},d);
const nvv=nul?nul.v:null;
L.push({c:nvv==null?'x':(nvv<2.0?'g':nvv<2.35?'y':'r'),t:'เจ้าพระยา ปากคลองลาดพร้าว (นวลฉวี)',
v:nvv==null?'ไม่มีข้อมูล':nvv.toFixed(2)+' ม.',rule:'เขียว <2.0 / เหลือง <2.35 / แดง ≥2.35'});
let k2=D.canal_k2&&D.canal_k2.warn!=null?D.canal_k2:null;
let k2v=k2?k2.value:null;
if(k2&&k2v!=null){k2v=+k2v;L.push({c:k2v<k2.warn?'g':(k2v<k2.crit?'y':'r'),
t:'ปตร.คลองสองสายใต้ (เซ็นเซอร์ กทม. วันนี้)',v:k2v.toFixed(2)+' ม.',rule:'เกณฑ์ทางการ: เตือนภัย '+k2.warn+' / วิกฤต '+k2.crit})}
else{const kl=valAt(byKey('ปากคลอง2สายใต้')||{},d);const klv=kl?kl.v:null;
L.push({c:klv==null?'x':(klv<1.8?'g':klv<2.1?'y':'r'),t:'คลองหกวา ปากคลอง 2 (ตัวรับของซอย)',
v:klv==null?'ไม่มีข้อมูล':klv.toFixed(2)+' ม.',rule:'เขียว <1.8 / เหลือง <2.1 / แดง ≥2.1'})}
let rise=0,ok4=true;
['บางปะอิน','สามเสน'].forEach(k=>{const s=byKey(k);if(!s){ok4=false;return}
const a=valAt(s,d),b=valAt(s,prev);if(a&&b)rise+=a.v-b.v;else ok4=false});
L.push({c:!ok4?'x':(rise<=0?'g':(rise<=0.10?'y':'r')),t:'มวลน้ำเหนือ (บางปะอิน+สามเสน เทียบเมื่อวาน)',
v:!ok4?'ไม่มีข้อมูล':(rise*100).toFixed(0)+' ซม./วัน',rule:'เขียว ไม่ขึ้น / เหลือง ≤+10 / แดง >+10 ซม.'});
const tm=tideMult(d);L.push({c:tm>=0.75?'g':(tm>=0.6?'y':'r'),t:'น้ำหนุนทะเล (เฟสดวงจันทร์)',
v:'ตัวคูณการระบาย '+tm.toFixed(2),rule:'คำนวณจากเฟสจันทร์: spring tide ~0.45 = ระบายช้า, น้ำแล้ง 1.0'});
let n3=0,ok6=true;for(let j=-2;j<=0;j++){const v=rainNorth[addD(d,j)];if(v==null)ok6=false;else n3+=v}
L.push({c:!ok6?'x':lv(n3,15,40),t:'ฝนภาคเหนือ 3 วัน (เฉลี่ย 4 ลุ่ม)',
v:!ok6?'เกินช่วงพยากรณ์':n3.toFixed(0)+' มม.',rule:'เขียว ≤15 / เหลือง ≤40 / แดง >40 มม. (มวลน้ำถึง กทม. ใน ~3-7 วัน)'});
let dm=0,dn='';(D.dams||[]).forEach(x=>{if(x.pct>dm){dm=x.pct;dn=x.name}});
L.push({c:dm<85?'g':(dm<100?'y':'r'),t:'เขื่อนต้นน้ำ (สูงสุด: '+dn+', ข้อมูลวันนี้)',
v:dm.toFixed(1)+'% ความจุปกติ',rule:'เขียว <85% / เหลือง 85-100% / แดง >100% = ต้องระบายเพิ่ม'});
return L}

function render(){
document.getElementById('built').textContent=fmtD(D.today)+' '+D.built_at.slice(11,16)+' น.';
const t=tierOf(sel);
document.getElementById('dsel').textContent=fmtD(selDate());
const dn=document.getElementById('dnote');
dn.textContent=sel===todayIdx?'(วันนี้)':((sel-todayIdx)+' วัน'+(sel>todayIdx?'ข้างหน้า':'ก่อน'));
const tc=document.getElementById('dtier');
tc.textContent=tierName[t];tc.className='tierchip t'+t;
const L=lights();
document.getElementById('lights').innerHTML=L.map(l=>
'<div class="light"><div class="dot '+l.c+'"></div><div><div class="t">'+l.t+
'</div><div class="v">'+l.v+'</div><div class="v" style="font-size:.75rem">'+l.rule+'</div></div></div>').join('');
const g=L.filter(l=>l.c==='g').length,r=L.filter(l=>l.c==='r').length;
const V=document.getElementById('verdict');
if(sel<todayIdx){V.textContent='สรุปวันดังกล่าว (ข้อมูลวัดจริง ย้อนหลัง)';V.style.background='#f1f5f9';V.style.color='#334155'}
else if(r>=3){V.textContent='น้ำเสี่ยงทรงตัวหรือขึ้น'+(sel===todayIdx?' (ข้อมูลจริงวันนี้)':' (คาดการเชิงสถิติ)');V.style.background='#fee2e2';V.style.color='#991b1b'}
else if(g>=5){V.textContent='น้ำมีแนวโน้มลด'+(sel===todayIdx?' (ข้อมูลจริงวันนี้)':' (คาดการเชิงสถิติ)');V.style.background='#dcfce7';V.style.color='#166534'}
else{V.textContent='น้ำทรงตัว ระบายช้า'+(sel===todayIdx?' (ข้อมูลจริงวันนี้)':' (คาดการเชิงสถิติ)');V.style.background='#ffedd5';V.style.color='#9a3412'}
renderChips();renderChart();renderTable();renderVars();
document.querySelectorAll('.qbtns button').forEach(b=>b.classList.toggle('on',+b.dataset.q===sel-todayIdx))
}

// ---- station chips + chart ----
let curKey=null;
function renderChips(){const box=document.getElementById('stchips');
if(!curKey){const f=D.stations.find(s=>s.fc.length);if(f)curKey=f.key}
box.innerHTML=D.stations.filter(s=>s.hist.length||s.fc.length).map(s=>
'<button data-k="'+s.key+'" class="'+(s.key===curKey?'on':'')+'">'+(s.name.length>22?s.key:s.name)+'</button>').join('');
box.querySelectorAll('button').forEach(b=>b.onclick=()=>{curKey=b.dataset.k;renderChart();renderChips()})}

function renderChart(){const s=byKey(curKey);if(!s)return;
const W=920,H=340,PL=46,PR=10,PT=14,PB=26;
let lo=1e9,hi=-1e9;
s.hist.forEach(p=>{lo=Math.min(lo,p[1]);hi=Math.max(hi,p[1])});
s.fc.forEach(p=>{lo=Math.min(lo,p[2]);hi=Math.max(hi,p[3])});
if(s.normal!=null){lo=Math.min(lo,s.normal);hi=Math.max(hi,s.normal)}
const ref=s.warn!=null?s.warn:s.ref;if(ref){lo=Math.min(lo,ref);hi=Math.max(hi,ref)}
if(lo>hi){lo=0;hi=1}const pad=(hi-lo)*0.08||.1;lo-=pad;hi+=pad;
const X=i=>PL+(W-PL-PR)*i/(nAll-1), Y=v=>PT+(H-PT-PB)*(1-(v-lo)/(hi-lo));
let g='';
// gridlines + y labels
for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4,y=Y(v);
g+='<line x1="'+PL+'" y1="'+y+'" x2="'+(W-PR)+'" y2="'+y+'" stroke="#eef2f7"/>'+
'<text x="'+(PL-6)+'" y="'+(y+4)+'" text-anchor="end" font-size="11" fill="#94a3b8">'+v.toFixed(2)+'</text>'}
// x labels ทุก ~15 วัน
for(let i=0;i<nAll;i+=15){const d=dAt(i);
g+='<text x="'+X(i)+'" y="'+(H-6)+'" text-anchor="middle" font-size="11" fill="#94a3b8">'+d.slice(8)+'/'+d.slice(5,7)+'</text>'}
// tier boundaries + today
const tb=[todayIdx+D.nwp_days,todayIdx+D.seasonal_trust];
tb.forEach(i=>{if(i<nAll)g+='<line x1="'+X(i)+'" y1="'+PT+'" x2="'+X(i)+'" y2="'+(H-PB)+'" stroke="#cbd5e1" stroke-dasharray="2 4"/>'});
g+='<line x1="'+X(todayIdx)+'" y1="'+PT+'" x2="'+X(todayIdx)+'" y2="'+(H-PB)+'" stroke="#64748b" stroke-width="2"/>';
g+='<text x="'+(X(todayIdx)+3)+'" y="'+(PT+10)+'" font-size="10" fill="#64748b">วันนี้</text>';
// fc band + line
if(s.fc.length){let band=s.fc.map(p=>X(dOff(p[0]))+','+Y(p[3])).join(' ');
const rb=s.fc.slice().reverse().map(p=>X(dOff(p[0]))+','+Y(p[2])).join(' ');
g+='<polygon points="'+band+' '+rb+'" fill="rgba(234,88,12,.14)"/>';
g+='<path d="M'+s.fc.map(p=>X(dOff(p[0]))+','+Y(p[1])).join('L')+'" fill="none" stroke="var(--orange)" stroke-width="2" stroke-dasharray="6 3"/>'}
// hist line
if(s.hist.length)g+='<path d="M'+s.hist.map(p=>X(dOff(p[0]))+','+Y(p[1])).join('L')+'" fill="none" stroke="var(--teal)" stroke-width="2"/>';
// normal + threshold
if(s.normal!=null)g+='<line x1="'+PL+'" y1="'+Y(s.normal)+'" x2="'+(W-PR)+'" y2="'+Y(s.normal)+'" stroke="var(--blue)" stroke-dasharray="5 4"/>'+
'<text x="'+(W-PR)+'" y="'+(Y(s.normal)-3)+'" text-anchor="end" font-size="10" fill="var(--blue)">ปกติ '+s.normal.toFixed(2)+'</text>';
if(ref!=null)g+='<line x1="'+PL+'" y1="'+Y(ref)+'" x2="'+(W-PR)+'" y2="'+Y(ref)+'" stroke="var(--red)" stroke-dasharray="5 4"/>'+
'<text x="'+(W-PR)+'" y="'+(Y(ref)-3)+'" text-anchor="end" font-size="10" fill="var(--red)">'+(s.warn!=null?'วิกฤต ':'ตลิ่ง ')+ (+ref).toFixed(2)+'</text>';
// selected day
g+='<line x1="'+X(sel)+'" y1="'+PT+'" x2="'+X(sel)+'" y2="'+(H-PB)+'" stroke="#111" stroke-width="1.5"/>';
// hover info
g+='<text id="htip" x="0" y="0" font-size="11" fill="#334155"></text>';
document.getElementById('chart').innerHTML='<svg viewBox="0 0 '+W+' '+H+'" id="svg">'+g+'</svg>';
const svg=document.getElementById('svg');
svg.onmousemove=e=>{const r=svg.getBoundingClientRect();const xr=(e.clientX-r.left)*W/r.width;
let i=Math.round((xr-PL)/(W-PL-PR)*(nAll-1));i=Math.max(0,Math.min(nAll-1,i));
const d=dAt(i),v=valAt(s,d);const tip=document.getElementById('htip');
if(v){tip.setAttribute('x',Math.min(W-160,PL+4));tip.setAttribute('y',PT+10);
tip.textContent=d+' '+(v.src==='h'?'จริง ':'คาด ')+v.v.toFixed(2)+(v.lo?' ('+v.lo+'-'+v.hi+')':'')}else tip.textContent=''};
svg.onclick=e=>{const r=svg.getBoundingClientRect();const xr=(e.clientX-r.left)*W/r.width;
let i=Math.round((xr-PL)/(W-PL-PR)*(nAll-1));i=Math.max(0,Math.min(nAll-1,i));scrub.value=i;sel=i;render()};
renderRain()}

function renderRain(){const W=920,H=70,PL=46,PR=10,PT=6,PB=14;
const mx=Math.max(5,...D.rain_soi.map(p=>p[1]));
const X=i=>PL+(W-PL-PR)*i/(nAll-1), Y=v=>PT+(H-PT-PB)*(1-v/mx);
let g='<line x1="'+PL+'" y1="'+(H-PB)+'" x2="'+(W-PR)+'" y2="'+(H-PB)+'" stroke="#cbd5e1"/>';
D.rain_soi.forEach(p=>{const i=dOff(p[0]);if(i<0||i>=nAll)return;const fc=p[0]>D.today;
g+='<rect x="'+(X(i)-2)+'" y="'+Y(p[1])+'" width="4" height="'+(H-PB-Y(p[1]))+'" fill="'+(fc?'#fdba74':'#94a3b8')+'" rx="1"/>'});
g+='<text x="'+PL+'" y="'+(PT+8)+'" font-size="10" fill="#94a3b8">สูงสุด '+mx.toFixed(0)+' มม.</text>';
document.getElementById('rain').innerHTML='<svg viewBox="0 0 '+W+' '+H+'">'+g+'</svg>'}

// ---- table ----
function renderTable(){const d=selDate(),prev=addD(d,-1),t=tierOf(sel);
let h='<tr><th>สถานี</th><th>ระดับ (ม.)</th><th>เทียบเมื่อวาน</th><th>เทียบปกติ</th><th>ช่วงคาด</th><th>ที่มา</th></tr>';
D.stations.filter(s=>s.fc.length||s.hmap[d]!==undefined).forEach(s=>{
const a=valAt(s,d),b=valAt(s,prev);if(!a)return;
const dv=b?((a.v-b.v)*100).toFixed(0)+' ซม.':'';
const nm=s.normal;let cls='ok',cmp='';
if(nm!=null){const x=(a.v-nm)*100;cmp=(x>=0?'+':'')+x.toFixed(0)+' ซม.';
cls=Math.abs(x)<10?'ok':(x<40?'hi':'crit')}
else{cls='ok';cmp='-'}
if(s.warn!=null&&a.v>=s.warn)cls='crit';
h+='<tr><td>'+s.name+'</td><td><b>'+a.v.toFixed(2)+'</b></td><td>'+dv+'</td>'+
'<td><span class="pill '+cls+'">'+cmp+'</span></td>'+
'<td>'+(a.lo!=null?a.lo.toFixed(2)+' - '+a.hi.toFixed(2):'-')+'</td>'+
'<td>'+(a.src==='h'?'วัดจริง':'คาดการ T'+a.tier)+'</td></tr>'});
document.getElementById('tbl').innerHTML=h}

// ---- variables panel ----
function renderVars(){const d=selDate();
const items=[
['ระดับน้ำจริงเริ่มต้น (h0)','ค่าเฉลี่ยอ่าน 18 ชม. ล่าสุดของแต่ละสถานี กลบวัฏจักรน้ำหนุนรายวัน','thaiwater',''],
['แรงฉุด (momentum, v0)','แนวโน้มขึ้น/ลงจาก 18 ชม. ก่อน อิทธิพลจางลงใน ~2 วัน','คำนวณเอง','v_bpa '+(D.v_bpa>0?'+':'')+D.v_bpa+' ม./วัน'],
['ฝนที่ซอย (วัน 1-16)','ฝนพยากรณ์รายวันที่พิกัดซอย ป้อน rise ของทุกสถานี','Open-Meteo NWP',rainSoi[d]!=null?rainSoi[d].toFixed(1)+' มม. (วันที่เลือก)':'-'],
['ฝนภาคเหนือ lag 3 วัน','ฝนเฉลี่ย 4 จุด (เชียงใหม่ น่าน สุโขทัย นครสวรรค์) มวลน้ำถึง กทม. ใน ~3 วัน','Open-Meteo NWP',rainNorth[addD(d,-3)]!=null?rainNorth[addD(d,-3)].toFixed(1)+' มม. (d-3)':'-'],
['ฝน seasonal (วัน 17-35)','ECMWF SEAS5 เรียบด้วย rolling mean 5 วัน เป็นสถานการณ์คาดหมาย','Open-Meteo Seasonal',''],
['สถิติฤดูกาล (วัน 36-90)','SEAS5 ระยะไกลเสื่อมสภาพ อ่านเป็นแนวโน้มเท่านั้น','climatology',''],
['wave บางปะอิน','ส่วนเกินเหนือตลิ่งบางปะอิน x0.30 ลากลงมา 1 วัน ต่อตอน = มวลน้ำเหนือ','คำนวณเอง','เหนือตลิ่ง '+(D.bpa_excess>0?'+':'')+D.bpa_excess+' ม.'],
['น้ำไหลเข้าเขื่อน (ใหม่)','ภูมิพล+สิริกิติ์ รวมกัน เกิน 150 ล้าน ลบ.ม./วัน = กดดันให้ต้องระบาย หนุนบางปะอินใน 3-8 วัน (ยังไม่ calibrate)','thaiwater analyst/dam',(D.dam_inflow_mcm||0).toFixed(0)+' ล้าน ลบ.ม./วัน'],
['ตัวคูณน้ำหนุน','คำนวณจากเฟสดวงจันทร์ spring ~0.45 (ระบายช้า) ถึง neap 1.0','ดาราศาสตร์','วันที่เลือก '+tideMult(d).toFixed(2)],
['K, rain_coef ต่อสถานี','อัตราร่อง/recession ตั้งมือจากสถิติน้ำหลากปี 2554 ยังไม่ fit จากข้อมูลจริง','สถิติปี 2554',''],
];
document.getElementById('vars').innerHTML=items.map(v=>'<div class="var"><div class="n">'+v[0]+
'</div><div class="val">'+v[3]+'</div><div class="d">'+v[1]+'<br><span class="src">แหล่ง: '+v[2]+'</span></div></div>').join('');
document.getElementById('fcnote').textContent=D.fcNote}

// ---- dams (สีตามเกณฑ์เดียวกับแผนที่: เขียว <85 / ส้ม 85-100 / แดง >100) ----
const damCls = p => p == null ? 'ok' : (p < 85 ? 'ok' : (p < 100 ? 'warm' : 'hot'));
document.getElementById('damskey').innerHTML=(D.dams||[]).map(x=>
'<div class="dam"><span style="width:70px">'+x.name+'</span><div class="bar"><i style="width:'+
Math.min(130,x.pct/1.3)+'%" class="'+damCls(x.pct)+'"></i></div><span>'+x.pct.toFixed(0)+
'% · ไหลเข้า '+(x.inflow!=null?(+x.inflow).toFixed(0):'-')+' · ระบาย '+(x.released!=null?(+x.released).toFixed(0):'-')+' ล้าน ลบ.ม./วัน</span></div>').join('');
document.getElementById('damstop').innerHTML=(D.dams_top||[]).map(x=>
'<div class="dam"><span style="width:70px;font-size:.8rem">'+x.name+'</span><div class="bar"><i style="width:'+
Math.min(130,x.pct/1.3)+'%" class="'+damCls(x.pct)+'"></i></div><span>'+x.pct.toFixed(0)+'%</span></div>').join('');

// ---- near sensors ----
(function(){const c=(D.canals||[]),r=(D.roads||[]);let h='';
if(c.length){h+='<div style="font-weight:600;font-size:.9rem">เซ็นเซอร์คลอง กทม.</div>'+
c.map(x=>'<div class="mut">'+x.name+' · '+x.value+' ม. (เตือนภัย '+x.warn+' / วิกฤต '+x.crit+') · '+x.dt.slice(5,16)+'</div>').join('')}
if(r.length){h+='<div style="font-weight:600;font-size:.9rem;margin-top:8px">ถนนที่มีน้ำท่วมขัง</div>'+
r.map(x=>'<div class="mut">'+x.name+' · '+x.cm+' ซม. · '+x.dt.slice(5,16)+'</div>').join('')}
if(!h)h='<div class="mut">เซ็นเซอร์ กทม. ไม่ส่งข้อมูลวันนี้ (feed ขัดข้องตั้งแต่เช้า) ไฟดวงที่ 3 ใช้สถานีกรมชลประทานแทน</div>';
document.getElementById('near').innerHTML=h})();

render();
</script>
</body></html>
"""

# เติม meta ที่ JS ต้องใช้ก่อน embed
DATA["histStart"] = None
DATA["fcEnd"] = fc["dates"][-1] if fc.get("dates") else None
DATA["fcNote"] = fc.get("note", "")
first_hist = sorted({p[0] for s in stations for p in s["hist"]})
DATA["histStart"] = first_hist[0] if first_hist else (fc["dates"][0] if fc.get("dates") else None)

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
out = os.path.join(BASE, "dashboard-saimai.html")
open(out, "w").write(html)
print("OK", out, f"| stations={len(stations)} (fc={sum(1 for s in stations if s['fc'])}) "
      f"| hist {DATA['histStart']} -> fc {DATA['fcEnd']}")
