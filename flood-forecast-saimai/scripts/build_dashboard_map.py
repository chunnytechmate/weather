#!/usr/bin/env python3
"""ประกอบ dashboard-map.html: แผนที่เขื่อนทั่วประเทศ + โซนผลกระทบตามลุ่มน้ำ
   กดเขื่อนแล้วขึ้นการ์ดบอกว่าผลกระทบถึงจังหวัด/พื้นที่ไหน มี lag เท่าไหร่
   และ (กรณีลุ่มเจ้าพระยา) ไฮไลต์สถานีสายหลักที่สะท้อนผลบนแผนที่

   การใช้ trackpad (แก้ปัญหาเดิมที่ 2 นิ้วเลื่อนกลายเป็นซูม):
   - สองนิ้วเลื่อน = เลื่อนหน้าเว็บตามปกติ (scrollWheelZoom: 'ctrl')
   - ถ่างนิ้ว (pinch) = ซูม เพราะ macOS ส่ง pinch มาเป็น ctrl+wheel
   - หรือกด Ctrl/Cmd ค้างแล้วเลื่อน = ซูม · ลาก 1 นิ้ว = เลื่อนแผนที่"""
import json, glob, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def latest(path):
    fs = sorted(glob.glob(os.path.join(BASE, "data", path)))
    return json.load(open(fs[-1])) if fs else {}

sn = latest("snapshots/snapshot-*.json")
fc = json.load(open(os.path.join(BASE, "data", "fc_days.json")))
hist = json.load(open(os.path.join(BASE, "data", "station_history.json")))
if not sn:
    raise SystemExit("ไม่มี snapshot")

# ---- โซนผลกระทบตามลุ่มน้ำ (ความสัมพันธ์ทางภูมิศาสตร์ คงที่ ไม่ใช่พยากรณ์) ----
# bkk = ผลต่อน้ำหน้าบ้าน (ซอยสายไหม): สูง = ลุ่มเจ้าพระยารวมกันแล้วถึง กทม.
BASIN_ZONES = {
    "ปิง": {"bkk": "สูง", "via": "แม่ปิง → นครสวรรค์ → เจ้าพระยา",
            "zones": ["ตาก → กำแพงเพชร → นครสวรรค์ (แม่ปิง)",
                      "เจ้าพระยาตอนล่าง: ชัยนาท สิงห์บุรี อ่างทอง อยุธยา",
                      "นนทบุรี → กรุงเทพฯ → ฉะเชิงเทรา"], "lag": "~4-7 วัน"},
    "น่าน": {"bkk": "สูง", "via": "แม่น่าน → นครสวรรค์ → เจ้าพระยา",
             "zones": ["อุตรดิตถ์ → พิษณุโลก → นครสวรรค์ (แม่น่าน)",
                       "เจ้าพระยาตอนล่าง: ชัยนาท สิงห์บุรี อ่างทอง อยุธยา",
                       "นนทบุรี → กรุงเทพฯ → ฉะเชิงเทรา"], "lag": "~4-7 วัน"},
    "วัง": {"bkk": "สูง (เล็กกว่าปิง/น่าน)", "via": "แม่วง → รวมแม่น่านที่อุตรดิตถ์ → นครสวรรค์",
            "zones": ["ลำปาง → อุตรดิตถ์ (แม่วง)", "นครสวรรค์ลงมาตามเจ้าพระยา",
                      "นนทบุรี → กรุงเทพฯ → ฉะเชิงเทรา"], "lag": "~4-7 วัน"},
    "ยม": {"bkk": "ปานกลาง", "via": "แม่ยม → นครสวรรค์ → เจ้าพระยา",
           "zones": ["แพร่ → สุโขทัย → นครสวรรค์ (แม่ยม)", "เจ้าพระยาตอนล่างถึง กทม."],
           "lag": "~4-7 วัน"},
    "สะแกกรัง": {"bkk": "ปานกลาง", "via": "แม่สะแกกรัง → นครสวรรค์ → เจ้าพระยา",
                 "zones": ["กำแพงเพชร → นครสวรรค์ (สะแกกรัง)", "เจ้าพระยาตอนล่างถึง กทม."],
                 "lag": "~4-7 วัน"},
    "ป่าสัก": {"bkk": "เล็กน้อย", "via": "แม่ป่าสัก → รวมเจ้าพระยาที่อยุธยา",
               "zones": ["เพชรบูรณ์ → ลพบุรี → สระบุรี → อยุธยา (ป่าสัก)",
                         "รวมเจ้าพระยาที่อยุธยา ผลต่อ กทม. เล็กน้อย"], "lag": "~2-4 วัน"},
    "มูล": {"bkk": "ไม่มี (คนละลุ่มกับเจ้าพระยา)", "via": "แม่มูล → รวมโขงที่อุบลฯ",
            "zones": ["นครราชสีมา บุรีรัมย์ สุรินทร์ (ลำตะคอง/ลำชี)", "ยโสธร์ อุบลราชธานี (แม่มูล)"], "lag": "-"},
    "ชี": {"bkk": "ไม่มี (คนละลุ่มกับเจ้าพระยา)", "via": "แม่ชี → รวมมูลที่ยโสธร์",
           "zones": ["ขอนแก่น ชัยภูมิ มหาสารคาม (แม่ชี)", "ร้อยเอ็ด → ยโสธร์ (ปากชี)"], "lag": "-"},
    "โขง": {"bkk": "ไม่มี (คนละลุ่มกับเจ้าพระยา)", "via": "ลุ่มโขงฝั่งไทย",
            "zones": ["หนองคาย บึงกาฬ หนองบัวลำภู อุดรธานี (ลำน้ำโขงฝั่งไทย)"], "lag": "-"},
    "ชายฝั่งทะเลตะวันออก": {"bkk": "ไม่มี", "via": "ลำน้ำสั้นลงทะเลอ่าวไทยโดยตรง",
                   "zones": ["ระยอง ชลบุรี (ลุ่มหัวไร่ปลายนา)", "ฉะเชิงเทรา (บางปะกงตอนล่าง)"], "lag": "-"},
    "บางปะกง": {"bkk": "ไม่มี", "via": "แม่บางปะกง → อ่าวไทย",
                "zones": ["นครนายก ปราจีนบุรี (บางปะกงตอนบน)", "ฉะเชิงเทรา (บางปะกงตอนล่าง)"], "lag": "-"},
    "แม่กลอง": {"bkk": "ไม่มี", "via": "แม่กลอง → อ่าวไทย",
                "zones": ["กาญจนบุรี (แควใหญ่/แควน้อย)", "ราชบุรี สมุทรสงครา (แม่กลอง)"], "lag": "-"},
    "เพชรบุรี": {"bkk": "ไม่มี", "via": "แม่เพชรบุรี → อ่าวไทย",
                 "zones": ["เพชรบุรี", "ประจวบคีรีขันธ์"], "lag": "-"},
    "ท่าจีน": {"bkk": "ไม่มี (แยกจากเจ้าพระยาที่ชัยนาท)", "via": "แม่ท่าจีน → อ่าวไทย",
              "zones": ["ชัยนาท (ทางแยกน้ำ)", "สุพรรณบุรี นครปฐม สมุทรสาคร"], "lag": "-"},
    "ภาคใต้ฝั่งตะวันออกตอนบน": {"bkk": "ไม่มี", "via": "ลุ่มสั้นลงอ่าวไทย",
                     "zones": ["สุราษฎร์ธานี"], "lag": "-"},
    "ภาคใต้ฝั่งตะวันออกตอนล่าง": {"bkk": "ไม่มี", "via": "ลุ่มสั้นลงอ่าวไทย",
                     "zones": ["สงขลา ปัตตานี ยะลา นราธิวาส"], "lag": "-"},
}

def zone_of(basin):
    for k, v in BASIN_ZONES.items():
        if k in (basin or ""):
            return v
    return {"bkk": "ไม่มีข้อมูลลุ่มน้ำ", "via": "-", "zones": [basin or "ไม่ระบุ"], "lag": "-"}

# สถานีเจ้าพระยาสายหลักตอนล่าง ที่สะท้อนผล release ของเขื่อนลุ่มเจ้าพระยา
CPY_KEYS = ["ค่ายจิรประวัติ", "สะพานธรรมจักร", "ท้ายเขื่อนเจ้าพระยา", "สรรพยา", "พรหมบุรี",
            "เมืองอ่างทอง", "บ้านบางแก้ว", "พระนครศรีอยุธยา", "บ้านป้อม", "บางปะอิน",
            "สามเสน", "สะพานกรุงเทพ", "สะพานนวลฉวี", "ปากคลองพระองค์เจ้า"]
MAINSTEM = CPY_KEYS  # เรียงเหนือ → ใต้ ใช้วาดเส้นแม่น้ำด้วย

DAM_DETAIL = {
    "ภูมิพล": "เขื่อนใหญ่สุดของลุ่มปิง คู่กับสิริกิติ์ เป็นตัวคุมน้ำเข้าเจ้าพระยาหลัก (ความจุ 13,462 ล้าน ลบ.ม.)",
    "สิริกิติ์": "เขื่อนใหญ่สุดของลุ่มน่าน คู่กับภูมิพล คุมมวลน้ำอีกครึ่งของเจ้าพระยา (ความจุ 17,745 ล้าน ลบ.ม.)",
    "กิ่วลม": "เขื่อนกักน้ำตอนบนของแม่วง ขนาดเล็กกว่าสองตัวหลักมาก",
    "แม่มอก": "เขื่อนเล็กบนแม่ยม (สุโขทัย)",
}

dams = []
for d in sn.get("dams_all", []):
    z = zone_of(d.get("basin", ""))
    rec = {"name": d["name"], "lat": d.get("lat"), "lon": d.get("lon"),
           "pct": d.get("storage_pct"), "inflow": d.get("inflow"),
           "released": d.get("released"), "released_mcm": d.get("released_mcm"),
           "spill": d.get("spill"),
           "basin": d.get("basin", ""), "province": d.get("province", ""),
           "agency": d.get("agency", ""), "max_storage": d.get("max_storage_mcm"),
           "bkk": z["bkk"], "via": z["via"], "zones": z["zones"], "lag": z["lag"]}
    if z["bkk"].startswith("สูง") or z["bkk"] == "ปานกลาง" or d["name"] in DAM_DETAIL:
        rec["hl"] = CPY_KEYS
    if d["name"] in DAM_DETAIL:
        rec["detail"] = DAM_DETAIL[d["name"]]
    dams.append(rec)

# ---- สถานี (มี normals จาก normal_levels ผ่าน station_history) ----
hist_st = hist.get("stations", {})
def normal_of(key, name):
    if key in hist_st:
        return hist_st[key].get("normal")
    for hk, hv in hist_st.items():
        if key in hk or hk in name:
            return hv.get("normal")
    return None

stations = []
for s in sn.get("stations", []):
    stations.append({"key": s["key"], "name": s["name"], "grp": s["group"],
                     "lat": s.get("lat"), "lon": s.get("lon"), "msl": s.get("msl"),
                     "bank": s.get("bank"), "dt": s.get("dt"),
                     "normal": normal_of(s["key"], s["name"])})

mainstem_ll = []
st_by_key = {s["key"]: s for s in stations}
for k in MAINSTEM:
    s = st_by_key.get(k)
    if s and s.get("lat") is not None:
        mainstem_ll.append([s["lat"], s["lon"]])

DATA = {"built_at": sn["fetched_at"], "dams": dams, "stations": stations,
        "mainstem": mainstem_ll, "home": [13.9175, 100.6512],
        "fc_note": fc.get("note", "")}

HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>แผนที่เขื่อน + โซนผลกระทบ (ลุ่มน้ำไทย)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--ink:#1e293b;--sub:#64748b;--line:#e2e8f0;--teal:#0d9488;--red:#dc2626}
*{box-sizing:border-box}
html,body{margin:0;height:100%;font-family:-apple-system,"Sarabun","Noto Sans Thai",sans-serif;color:var(--ink)}
#bar{position:fixed;top:0;left:0;right:0;z-index:1000;background:#fff;border-bottom:1px solid var(--line);
padding:8px 14px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
#bar b{font-size:1.02rem}
#bar .mut{color:var(--sub);font-size:.78rem}
#map{position:absolute;top:52px;bottom:0;left:0;right:0}
#panel{position:absolute;top:64px;right:12px;z-index:1000;width:330px;max-width:calc(100% - 24px);
max-height:calc(100% - 90px);overflow:auto;background:#fff;border:1px solid var(--line);border-radius:12px;
padding:12px 14px;display:none;box-shadow:0 4px 18px rgba(15,23,42,.08)}
#panel h3{margin:.1em 0;font-size:1.05rem}
#panel .close{float:right;cursor:pointer;color:var(--sub);border:1px solid var(--line);border-radius:6px;
padding:0 8px;font-size:.85rem}
.zl{font-size:.88rem;margin:3px 0;padding-left:14px;position:relative}
.zl:before{content:"";position:absolute;left:2px;top:7px;width:7px;height:7px;border-radius:50%;background:var(--teal)}
.chip{display:inline-block;font-size:.75rem;padding:2px 10px;border-radius:999px;margin:1px 3px 1px 0;
border:1px solid var(--line);cursor:pointer;background:#fff}
.chip:hover{border-color:var(--teal);color:var(--teal)}
.tag{display:inline-block;font-size:.72rem;padding:1px 9px;border-radius:999px;margin-left:6px}
.hi{background:#fee2e2;color:#b91c1c}.md{background:#ffedd5;color:#c2410c}.lo{background:#f1f5f9;color:#475569}
#legend{position:absolute;bottom:14px;left:12px;z-index:1000;background:#fff;border:1px solid var(--line);
border-radius:10px;padding:8px 12px;font-size:.78rem;line-height:1.9}
.sw{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}
a{color:#2563eb}
.leaflet-container{font:inherit}
</style>
</head>
<body>
<div id="bar">
  <b>แผนที่เขื่อน + โซนผลกระทบ</b>
  <span class="mut">กดที่เขื่อน (วงกลม) เพื่อดูว่าระบายน้ำแล้วกระทบจังหวัด/พื้นที่ไหน ·
  สถานีวัดระดับ = จุดฟ้าเล็ก · อัปเดต <span id="bt"></span> ·
  <a href="dashboard.html">dashboard กราฟ</a></span>
  <span class="mut" style="flex-basis:100%">trackpad: สองนิ้วเลื่อน = เลื่อนหน้า ·
  ถ่างนิ้ว หรือ Ctrl/Cmd+เลื่อน = ซูม · ลาก 1 นิ้ว = เลื่อนแผนที่</span>
</div>
<div id="map"></div>
<div id="panel"></div>
<div id="legend">
  <span class="sw" style="background:#16a34a"></span>เขื่อน &lt;85% ความจุ
  <span class="sw" style="background:#d97706"></span>85-100%
  <span class="sw" style="background:#dc2626"></span>&gt;100% (ต้องระบายเพิ่ม)<br>
  <span class="sw" style="background:#0d9488"></span>สถานีระดับน้ำ
  <span class="sw" style="background:#111;height:4px;border-radius:2px;width:16px"></span>บ้าน (ซอยสายไหม 44)
  <span class="sw" style="background:#60a5fa;height:3px;border-radius:2px;width:16px"></span>เจ้าพระยาสายหลัก
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
document.getElementById('bt').textContent = D.built_at.slice(0, 16).replace('T', ' ');

// trackpad: 'ctrl' = ซูมเฉพาะเมื่อ pinch (macOS ส่งมาเป็น ctrl+wheel) หรือผู้ใช้กด Ctrl/Cmd
// สองนิ้วเลื่อนปกติจึงเลื่อนหน้าเว็บ ไม่ถูกแผนที่กลืน
const map = L.map('map', {scrollWheelZoom: 'ctrl'}).setView([15.5, 100.8], 6);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 12, attribution: '&copy; OpenStreetMap'
}).addTo(map);

L.polyline(D.mainstem, {color: '#60a5fa', weight: 4, opacity: .75}).addTo(map);

const stMarkers = {};
D.stations.forEach(s => {
  if (s.lat == null) return;
  const m = L.circleMarker([s.lat, s.lon], {radius: 4, color: '#fff', weight: 1,
    fillColor: '#0d9488', fillOpacity: .95}).addTo(map);
  let tip = '<b>' + s.name + '</b><br>ระดับ ' + (s.msl != null ? s.msl.toFixed(2) + ' ม.' : '-') +
    (s.normal != null ? ' (ปกติ ' + s.normal.toFixed(2) + ')' : '');
  if (s.bank) tip += '<br>ระดับตลิ่ง ' + s.bank.toFixed(2) + ' ม.';
  m.bindTooltip(tip);
  stMarkers[s.key] = m;
});
const home = L.circleMarker(D.home, {radius: 8, color: '#fff', weight: 2,
  fillColor: '#111', fillOpacity: 1}).addTo(map);
home.bindTooltip('<b>บ้าน (ซอยสายไหม 44)</b>');

let hlLayer = null;
function clearHl() {
  if (hlLayer) { map.removeLayer(hlLayer); hlLayer = null }
  Object.values(stMarkers).forEach(m => m.setStyle({fillColor: '#0d9488', radius: 4}))
}

D.dams.forEach(d => {
  if (d.lat == null) return;
  const col = d.pct == null ? '#94a3b8' : (d.pct < 85 ? '#16a34a' : (d.pct < 100 ? '#d97706' : '#dc2626'));
  const mk = L.circleMarker([d.lat, d.lon], {radius: 9, color: '#fff', weight: 2,
    fillColor: col, fillOpacity: .95}).addTo(map);
  mk.bindTooltip('<b>' + d.name + '</b> ' + (d.pct != null ? d.pct.toFixed(0) + '%' : ''));
  mk.on('click', () => showDam(d));
});

const panel = document.getElementById('panel');
function showDam(d) {
  const bkkTag = d.bkk.startsWith('สูง') ? 'hi' : (d.bkk === 'ปานกลาง' || d.bkk === 'เล็กน้อย' ? 'md' : 'lo');
  let h = '<span class="close" onclick="document.getElementById(\'panel\').style.display=\'none\';clearHl()">ปิด X</span>';
  h += '<h3>' + d.name + '</h3>';
  h += '<div style="font-size:.82rem;color:var(--sub)">' + d.agency + ' · ' + d.basin + ' · จ.' + d.province + '</div>';
  if (d.detail) h += '<div style="font-size:.82rem;margin-top:4px">' + d.detail + '</div>';
  h += '<div style="margin:8px 0;font-size:.9rem"><b>' + (d.pct != null ? d.pct.toFixed(1) : '-') + '%</b> ความจุปกติ' +
       ' · ไหลเข้า ' + (d.inflow != null ? (+d.inflow).toFixed(0) : '-') +
       ' · ระบาย ' + (d.released_mcm != null ? (+d.released_mcm).toFixed(1) : '-') +
       (d.spill ? ' · spill ' + d.spill : '') + ' ล้าน ลบ.ม./วัน</div>';
  if (d.released != null && +d.released > 0)
    h += '<div class="mut" style="font-size:.75rem">ใช้น้ำสะสมตั้งแต่ต้นปี ~' + (+d.released).toFixed(0) + ' ล้าน ลบ.ม.</div>';
  h += '<div style="font-weight:700;font-size:.88rem;margin-top:8px">โซนที่มีผลกระทบ' +
       '<span class="tag ' + bkkTag + '">ผลต่อน้ำหน้าบ้าน: ' + d.bkk + '</span></div>';
  h += '<div class="mut" style="font-size:.75rem">ความสัมพันธ์ทางลุ่มน้ำ (คงที่) ไม่ใช่พยากรณ์' +
       (d.lag !== '-' ? ' · น้ำถึง กทม. ใน ' + d.lag : '') + '</div>';
  h += '<div style="margin:4px 0">' + d.zones.map(z => '<div class="zl">' + z + '</div>').join('') + '</div>';
  if (d.via && d.via !== '-') h += '<div class="mut" style="font-size:.78rem">เส้นทางน้ำ: ' + d.via + '</div>';
  if (d.hl) {
    h += '<div style="font-weight:700;font-size:.85rem;margin-top:8px">สถานีที่สะท้อนผล (กดเพื่อบินไป)</div><div>';
    d.hl.forEach(k => { const s = stMarkers[k]; if (s) {
      h += '<span class="chip" data-k="' + k + '">' + k + '</span>' } });
    h += '</div>';
    clearHl();
    hlLayer = L.layerGroup().addTo(map);
    const pts = [];
    d.hl.forEach(k => { const m = stMarkers[k]; if (m) {
      m.setStyle({fillColor: '#f59e0b', radius: 7}); m.bringToFront() } });
    D.stations.filter(s => d.hl.includes(s.key) && s.lat != null)
      .sort((a, b) => b.lat - a.lat).forEach(s => pts.push([s.lat, s.lon]));
    hlLayer.addLayer(L.polyline(pts, {color: '#ea580c', weight: 3, dashArray: '6 5'}));
    const bounds = L.latLngBounds([[d.lat, d.lon], ...pts]);
    map.fitBounds(bounds.pad(0.25));
  }
  panel.innerHTML = h;
  panel.style.display = 'block';
  panel.querySelectorAll('.chip').forEach(c => c.onclick = () => {
    const m = stMarkers[c.dataset.k]; if (m) { map.flyTo(m.getLatLng(), 10); m.openTooltip() }
  });
}
window.clearHl = clearHl;
</script>
</body></html>
"""

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
out = os.path.join(BASE, "dashboard-map.html")
open(out, "w").write(html)
print("OK", out, f"| dams={len(dams)} stations={len(stations)} mainstem_pts={len(mainstem_ll)}")
