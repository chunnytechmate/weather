#!/usr/bin/env python3
"""ประกอบ dashboard.html จาก snapshots ทั้งหมดใน data/snapshots/ (self-contained, offline)"""
import json, glob, os, html, datetime

TODAY_STR = datetime.date.today().isoformat()

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPS = sorted(glob.glob(os.path.join(BASE, "data", "snapshots", "snapshot-*.json")))

KEY_STATIONS = {
    "นวลฉวี": "สะพานนวลฉวี",
    "ปากคลอง2สายใต้": "คลองลาดพร้าว ปากคลอง2สายใต้",
    "สามเสน": "กรมชลประทานสามเสน",
    "บางปะอิน": "บางปะอิน",
}

def load_all():
    out = []
    for f in SNAPS:
        try:
            out.append(json.load(open(f)))
        except Exception:
            pass
    return out

def fnum(x, d=2):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def trend_sym(cur, prev):
    if cur is None or prev is None:
        return "—", "#888"
    dd = (cur - prev) * 100
    if dd > 1: return "▲ +" + f"{dd:.0f} ซม.", "#c62828"
    if dd < -1: return "▼ " + f"{dd:.0f} ซม.", "#2e7d32"
    return "— คงที่", "#666"

def level_color(msl, ref):
    if msl is None or not ref: return "#9e9e9e"
    pct = msl / ref
    if pct >= 1.0: return "#c62828"
    if pct >= 0.85: return "#ef6c00"
    if pct >= 0.70: return "#f9a825"
    return "#2e7d32"

def status_label(msl, ref, normal=None):
    if msl is None or not ref: return "ไม่มีข้อมูล", 0
    pct = msl / ref * 100
    if msl >= ref: lab = "ถึง/ล้นธงภัย"
    elif pct >= 85: lab = "ใกล้ธงภัย"
    elif pct >= 70: lab = "สูง"
    else: lab = "ปกติ"
    if normal is not None and msl < normal:
        lab = "ปกติ (ใกล้ค่าเฉลี่ย)"
    return lab, pct

def snapshot_p25(snaps):
    """p25 ของสถานีหลักจาก snapshot ของเราเอง — ใช้เป็น 'ปกติ' สำรองเมื่อไม่มีข้อมูลประวัติภายนอก"""
    p25 = {}
    days = sorted({sn["fetched_at"][:10] for sn in snaps})
    if len(days) < 14:
        return {}, len(days)
    for key in KEY_STATIONS:
        vals = []
        for sn in snaps:
            for st in sn["stations"]:
                if key in st["key"] or key in st["name"]:
                    vals.append(st["msl"])
        if len(vals) >= 20:
            vals.sort()
            p25[key] = vals[len(vals)//4]
    return p25, len(days)

def load_normals_ext():
    """ระดับน้ำปกติจากไฟล์ normal_levels.json (ประวัติ 60 วัน / เกณฑ์ทางการ)"""
    path = os.path.join(BASE, "data", "normal_levels.json")
    try:
        d = json.load(open(path))
        return d.get("stations") or {}, d.get("canals") or {}, d.get("built_at", "")
    except Exception:
        return {}, {}, ""

def norm_text(v, ref_msl, scale):
    """สร้าง (ข้อความใต้หลอด, html เส้นบนหลอด) สำหรับระดับปกติ"""
    if v is None:
        return "", ""
    diff = (ref_msl - v["normal"]) * 100
    dtxt = f"สูงกว่าปกติ +{diff:.0f} ซม." if diff >= 2 else (
        f"ต่ำกว่าปกติ {diff:.0f} ซม." if diff <= -2 else "≈ ปกติแล้ว")
    pos = min(99.5, max(0.5, v["normal"] / scale * 100))
    mark = (f'<div class="normmark" style="left:{pos:.1f}%" '
            f'title="ระดับปกติ ~{v["normal"]:.2f} ม. ({v.get("source", "")})"></div>')
    txt = (f' · <span style="color:#00838f">ปกติ ~{v["normal"]:.2f} ม. ({dtxt})</span>')
    return txt, mark

CRITICAL_LOCAL = {
    "ปากคลอง2สายใต้": 2.10,
    "ท้ายปตร.คลอง2": 1.95,
    "คลองเปรมประชากร หลักหก": 1.50,
    "คลองหกวา ลำลูกกา คลอง8": 2.00,
}

def station_rows(stations, first_map, p25=None, norm_ext=None):
    p25 = p25 or {}
    norm_ext = norm_ext or {}
    rows = []
    for s in sorted(stations, key=lambda x: -(x.get("lat") or 0)):
        msl, bank = s["msl"], s["bank"]
        crit = next((v for k, v in CRITICAL_LOCAL.items() if k in s["name"]), None)
        ref = crit if crit is not None else bank
        ref_name = "ระดับวิกฤตฝั่งเรา" if crit is not None else "ธงภัย"
        pct = min(100.0, msl / bank * 100) if bank else 60
        lab, ref_pct = status_label(msl, ref, p25.get(s["key"]))
        sym, col = trend_sym(msl, fnum(s.get("prev")))
        since0 = ""
        first = first_map.get(s["key"])
        if first is not None and msl is not None:
            d0 = (msl - first) * 100
            since0 = f" | ตั้งแต่เริ่มเก็บ: {'+' if d0>=0 else ''}{d0:.0f} ซม."
        if crit is not None:
            margin = f"เหลือ {(crit-msl)*100:.0f} ซม. ถึงระดับวิกฤตฝั่งเรา ({crit:.2f} ม.)"
        elif bank:
            margin = f"{(bank-msl)*100:.0f} ซม. ก่อนถึงธงภัย"
        else:
            margin = "—"
        # ระดับปกติ: เอาจาก normal_levels.json (ประวัติ 60 วัน) ก่อน, รองลงมือคือ p25 ของเรา
        nv = norm_ext.get(s["key"]) or ({"normal": p25[s["key"]], "source": "p25 snapshot ของเรา"}
                                        if s["key"] in p25 else None)
        ntxt, nmark = norm_text(nv, msl, bank) if bank else ("", "")
        rows.append(f"""
        <div class="row">
          <div class="rname">{html.escape(s['name'])}<span class="river">{html.escape(s['river'])}</span></div>
          <div class="rbar">
            <div class="track"><div class="fill" style="width:{pct:.1f}%;background:{level_color(msl,ref)}"></div>
            {nmark}<div class="bankmark" title="{ref_name} {ref if ref else '?'} ม."></div></div>
            <div class="rmeta"><b>{msl:.2f} ม.</b> = {ref_pct:.0f}% ของ{ref_name} ({margin}){ntxt} — <b>{lab}</b></div>
          </div>
          <div class="rtrend" style="color:{col}">{sym}<span class="since">{since0}</span></div>
        </div>""")
    return "\n".join(rows)

def rain_chart(wx_daily):
    t = wx_daily.get("time", [])
    v = [fnum(x) or 0 for x in wx_daily.get("precipitation_sum", [])]
    p = wx_daily.get("precipitation_probability_max", [0]*len(t))
    if not t: return "<p>ไม่มีข้อมูลฝน</p>"
    W, H, PAD, BW = 860, 240, 34, None
    n = len(t); bw = (W-2*PAD)/n*0.62
    mx = max(v + [10])
    bars = []
    today = datetime.date.today().isoformat()
    for i, (d, val, prob) in enumerate(zip(t, v, p)):
        x = PAD + (W-2*PAD)*(i+0.5)/n - bw/2
        h = (H-2*PAD-18) * val/mx
        y = H-PAD-18-h
        col = "#1565c0" if d < today else ("#64b5f6" if d == today else "#90caf9")
        lab = f"{int(d[8:10])}/{int(d[5:7])}"
        tag = "" if d <= today else " (พยากรณ์)"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h,0):.1f}" rx="3" fill="{col}"><title>{lab}: {val:.1f} มม.{tag}</title></rect>')
        bars.append(f'<text x="{x+bw/2:.1f}" y="{H-PAD-2}" font-size="11" text-anchor="middle" fill="#555">{lab}</text>')
        if val >= 1:
            bars.append(f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" font-size="10" text-anchor="middle" fill="#333">{val:.0f}</text>')
        if d > today:
            bars.append(f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" font-size="9" text-anchor="middle" fill="#777"> </text>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart">{"".join(bars)}</svg>'

def history_chart(snaps, label, key):
    per_day = {}
    for sn in snaps:
        d = sn["fetched_at"][:10]
        for st in sn["stations"]:
            if key in st["key"] or key in st["name"]:
                per_day.setdefault(d, []).append(st["msl"])
    days = sorted(per_day)
    if len(days) < 2:
        return f"<p class='hint'>{label}: กำลังสะสมข้อมูล (มี {len(days)} วัน) — กราฟจะเริ่มแสดงเมื่อเก็บได้ตั้งแต่ 2 วัน</p>"
    vals = [sum(vs)/len(vs) for vs in (per_day[d] for d in days)]
    W, H, PAD = 420, 190, 30
    n = len(days); bw = (W-2*PAD)/n*0.55
    lo, hi = min(vals)-0.1, max(vals)+0.1
    bars = []
    for i, (d, val) in enumerate(zip(days, vals)):
        x = PAD + (W-2*PAD)*(i+0.5)/n - bw/2
        h = (H-2*PAD-14) * (val-lo)/(hi-lo) if hi > lo else 10
        y = H-PAD-14-h
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h,1):.1f}" rx="3" fill="#00838f"><title>{d}: {val:.2f} ม.</title></rect>')
        bars.append(f'<text x="{x+bw/2:.1f}" y="{H-PAD-2}" font-size="10" text-anchor="middle" fill="#555">{int(d[8:10])}/{int(d[5:7])}</text>')
        bars.append(f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" font-size="10" text-anchor="middle" fill="#333">{val:.2f}</text>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart">{"", ""}{"".join(bars)}</svg><p class="cap">{label} (ม. MSL, เฉลี่ยรายวันจาก snapshot)</p>'

def traffic(snaps):
    if not snaps: return [], "—"
    sn = snaps[-1]
    st_by_key = {s["key"]: s for s in sn["stations"]}
    def g(k): return st_by_key.get(k)

    rain24 = 0.0
    times = sn.get("wx_hourly_time", []); precs = sn.get("wx_hourly_precip", [])
    now_iso = sn["fetched_at"][:13]
    for t, p in zip(times, precs):
        if t[:13] <= now_iso and t >= (datetime.datetime.fromisoformat(now_iso) - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H"):
            rain24 += p or 0

    def light(v, g1, y1):
        return "g" if v <= g1 else ("y" if v <= y1 else "r")

    l1 = light(rain24, 5, 20)
    nul = g("สะพานนวลฉวี"); nulv = nul["msl"] if nul else 9
    l2 = "g" if nulv < 2.0 else ("y" if nulv < 2.35 else "r")

    klong2 = next((c for c in sn.get("canals", []) if "คลองสอง" in c.get("name", "")), None)
    if klong2 and fnum(klong2.get("crit")):
        kv, kw, kc = fnum(klong2["value"]), fnum(klong2["warn"]), fnum(klong2["crit"])
        l3 = "g" if kv < kw else ("y" if kv < kc else "r")
        t3, v3 = "ปตร.คลองสองสายใต้ เซ็นเซอร์ กทม. (ทางการ)", f"{kv:.2f} ม. (เตือนภัย {kw} / วิกฤต {kc})"
        r3rule = "เขียว <เตือนภัย / เหลือง <วิกฤต / แดง ≥วิกฤต (เกณฑ์ทางการ กทม.)"
    else:
        klong = g("ปากคลอง2สายใต้") or g("คลองลาดพร้าว ปากคลอง2สายใต้")
        klv = klong["msl"] if klong else 9
        l3 = "g" if klv < 1.8 else ("y" if klv < 2.1 else "r")
        t3, v3 = "คลองหกวา ปากคลอง 2 (ตัวรับของซอย)", f"{klv:.2f} ม."
        r3rule = "เขียว <1.8 / เหลือง <2.1 / แดง ≥2.1"

    bpa = g("บางปะอิน"); ssn = g("กรมชลประทานสามเสน")
    rise = 0.0
    for s in (bpa, ssn):
        if s and s.get("prev") is not None:
            rise += (s["msl"] - s["prev"])
    l4 = "g" if rise <= 0 else ("y" if rise <= 0.10 else "r")
    detail4 = []
    for nm, s in (("บางปะอิน", bpa), ("สามเสน", ssn)):
        if s and s.get("prev") is not None:
            detail4.append(f"{nm} {(s['msl']-s['prev'])*100:+.0f} ซม. ({s.get('dt','')[5:16]})")

    d0 = datetime.date.today()
    l5 = "r" if d0 <= datetime.date(2026, 9, 29) else ("y" if d0 <= datetime.date(2026, 9, 30) else "g")

    north72 = 0.0
    for w in sn.get("wx_north", []):
        tt = w.get("time", []); pp = w.get("precip", [])
        for t, p in zip(tt, pp):
            if t >= TODAY_STR:
                try:
                    north72 += float(p or 0)
                except (TypeError, ValueError):
                    pass
    north72 = north72 / max(1, len(sn.get("wx_north", [])))
    l6 = light(north72, 15, 40)

    dam_max = 0.0; dam_nm = "—"
    for d in sn.get("dams", []):
        if (d.get("storage_pct") or 0) > dam_max:
            dam_max = d["storage_pct"]; dam_nm = d["name"]
    l7 = "g" if dam_max < 85 else ("y" if dam_max < 100 else "r")

    lights = [
        (l1, "ฝน 24 ชม. ที่ซอย", f"{rain24:.1f} มม.", "เขียว ≤5 / เหลือง ≤20 / แดง >20"),
        (l2, "เจ้าพระยา ปากคลองลาดพร้าว (นวลฉวี)", f"{nulv:.2f} ม. (ธงภัย 2.50)", "เขียว <2.0 / เหลือง <2.35 / แดง ≥2.35"),
        (l3, t3, v3, r3rule),
        (l4, "มวลน้ำเหนือ (บางปะอิน+สามเสน)", " · ".join(detail4), "เขียว ไม่ขึ้น / เหลือง +≤10 ซม. / แดง >+10"),
        (l5, "น้ำหนุนทะเล (spring tide)", "สูงสุด 27–29 ก.ย.", "แดง 27–29 ก.ย. / เหลือง 30 ก.ย. / เขียวหลังจากนั้น"),
        (l6, "ฝนภาคเหนือ 72 ชม. (ค่าเฉลี่ย 4 ลุ่ม)", f"{north72:.0f} มม./จุด", "เขียว ≤15 / เหลือง ≤40 / แดง >40 (มม. รวม 3 วัน)"),
        (l7, "เขื่อนต้นน้ำ (สูงสุด: " + dam_nm + ")", f"{dam_max:.1f}% ความจุปกติ", "เขียว <85% / เหลือง 85–100% / แดง >100%"),
    ]
    score = [l for l, *_ in lights]
    greens = score.count("g"); reds = score.count("r")
    if reds >= 3: verdict = ("น้ำฝั่งคุณเสี่ยงทรงตัวหรือขึ้น", "#c62828")
    elif greens >= 5: verdict = ("น้ำฝั่งคุณเดินลดชัดเจน", "#2e7d32")
    elif greens >= 3 and reds == 0: verdict = ("เริ่มมีแนวโน้มลด (ทรงตัว–ลดช้า)", "#ef6c00")
    else: verdict = ("ยังทรงตัว ระบายช้า", "#ef6c00")
    return lights, verdict

PROVINCE = {
    "เชียงดาว": "เชียงใหม่ อ.เชียงดาว (ปิงตอนบน)",
    "สะพานนวรัฐ": "เชียงใหม่ อ.เมือง (ปิง)",
    "อ.เมืองน่าน": "น่าน อ.เมือง (น่านตอนบน)",
    "เมืองแพร่": "แพร่ อ.เมือง (ยมตอนบน)",
    "สวรรคโลก": "สุโขทัย อ.สวรรคโลก (ยม)",
    "วัดเกยไชยเหนือ": "พิจิตร (น่านตอนล่าง)",
    "ชุมแสงสงคราม": "นครสวรรค์ อ.ชุมแสงสงคราม (ยมก่อนบรรจบ)",
    "คลองระพีพัฒน์แยกตก": "ปทุมธานี อ.ธัญบุรี (ระพีฯ)",
    "คลองระพีพัฒน์แยกใต้": "ปทุมธานี อ.หนองเสือ (ระพีฯ)",
    "สะพานเดชาติวงศ์": "นครสวรรค์ อ.เมือง",
    "ค่ายจิรประวัติ": "นครสวรรค์ อ.เมือง",
    "สะพานธรรมจักร": "นครสวรรค์ (วัดธรรมามูล)",
    "ท้ายเขื่อนเจ้าพระยา": "ชัยนาท อ.สรรพยา",
    "สรรพยา": "ชัยนาท อ.สรรพยา",
    "พรหมบุรี": "สิงห์บุรี อ.พรหมบุรี",
    "เมืองอ่างทอง": "อ่างทอง อ.เมือง",
    "บ้านบางแก้ว": "อ่างทอง อ.ป่าโมก",
    "พระนครศรีอยุธยา": "อยุธยา อ.เมือง",
    "บ้านป้อม": "อยุธยา อ.บางปะหัน",
    "บางปะอิน": "อยุธยา อ.บางปะอิน",
    "กรมชลประทานสามเสน": "กรุงเทพฯ (สามเสน)",
    "สะพานกรุงเทพ": "กรุงเทพฯ (สะพานพระราม 1)",
    "สะพานนวลฉวี": "กรุงเทพฯ (ปากคลองลาดพร้าว)",
    "ปากคลอง2สายใต้": "กรุงเทพฯ (คลองสอง หลักสี่-บางเขน)",
    "ท้ายปตร.คลอง2": "กรุงเทพฯ (คลองสอง)",
    "คลองเปรมประชากร หลักหก": "กรุงเทพฯ (หลักหก จตุจักร)",
    "คลองหกวา ลำลูกกา คลอง8": "ปทุมธานี (ลำลูกกา คลอง 8)",
    "ปากคลองพระองค์เจ้า": "สมุทรปราการ (บางบ่อ-บางพลี)",
    "คลองลัดบางยอ 1": "กรุงเทพฯ (จอมทอง-ราษฎร์บูรณะ)",
}
HOME = {"name": "บ้านคุณ — ท้ายซอยสายไหม 44", "lat": 13.9175, "lon": 100.6512}

def dam_rows(dams):
    rows = []
    for d in sorted(dams, key=lambda x: -x.get("storage_pct", 0)):
        pct = d.get("storage_pct") or 0
        col = "#c62828" if pct >= 100 else ("#f9a825" if pct >= 85 else "#2e7d32")
        lab = "เกินความจุปกติ" if pct >= 100 else ("ใกล้ความจุปกติ" if pct >= 85 else "ปกติ")
        try: rel = float(d.get("released") or 0)
        except ValueError: rel = 0
        try: inf = float(d.get("inflow") or 0)
        except ValueError: inf = 0
        rows.append(f"""
        <div class="row">
          <div class="rname">เขื่อน{html.escape(d['name'])}<span class="river">วันที่ข้อมูล {d.get('date','')}</span></div>
          <div class="rbar">
            <div class="track"><div class="fill" style="width:{min(pct,100):.1f}%;background:{col}"></div>
            <div class="bankmark" title="ความจุปกติ 100%"></div></div>
            <div class="rmeta"><b>{pct:.1f}%</b> ของความจุปกติ ({d.get('storage_mcm',0):,.0f} ลม.ม.) — <b>{lab}</b></div>
          </div>
          <div class="rtrend">ไหลเข้า {inf:,.1f}<span class="since">ใช้/ระบาย {rel:,.1f} ลม.ม./วัน</span></div>
        </div>""")
    return "\n".join(rows)

def canal_rows(canals):
    rows = []
    for c in canals:
        v = fnum(c.get("value")); w = fnum(c.get("warn")); k = fnum(c.get("crit"))
        col, pct, meta = "#9e9e9e", 50, "ไม่มีค่าอ้างอิง"
        nmark = ""
        if v is not None and k:
            pct = min(100.0, v / k * 100)
            col = "#c62828" if v >= k else ("#f9a825" if (w and v >= w) else "#2e7d32")
            lab = "เกินวิกฤต" if v >= k else ("เกินเตือนภัย" if (w and v >= w) else "ปกติ")
            meta = f"{v:.2f} ม. (เตือนภัย {w}, วิกฤต {k}) — <b>{lab}</b> ({pct:.0f}% ของวิกฤต)"
            if w is not None:
                nv = {"normal": w, "source": "เกณฑ์เตือนภัย กทม."}
                ntxt, nmark = norm_text(nv, v, k)
                meta += ntxt
        rows.append(f"""
        <div class="row">
          <div class="rname">{html.escape(c['name'])}<span class="river">ห่างจากซอย {c.get('dist_km','?')} กม.</span></div>
          <div class="rbar">
            <div class="track"><div class="fill" style="width:{pct:.1f}%;background:{col}"></div>
            {nmark}<div class="bankmark" title="ระดับวิกฤตทางการ"></div></div>
            <div class="rmeta">{meta}</div>
          </div>
          <div class="rtrend">{c.get('dt','')[11:16]} น.<span class="since">อ่าน {c.get('dt','')}</span></div>
        </div>""")
    return "\n".join(rows)

def road_rows(roads):
    if not roads:
        return "<p class='hint'>ไม่พบเซ็นเซอร์ถนนในรัศมี 7.5 กม. ที่อัปเดตวันนี้</p>"
    items = []
    for r in roads:
        cm = fnum(r.get("cm")) or 0
        col = "#2e7d32" if cm <= 0.5 else ("#f9a825" if cm <= 10 else "#c62828")
        txt = "แห้ง" if cm <= 0.5 else f"น้ำ {cm:.0f} ซม."
        items.append(f'<span class="roadchip" style="border-color:{col}"><b style="color:{col}">{txt}</b> · {html.escape(r["name"])} ({r.get("dist_km","?")} กม.)</span>')
    return f'<div class="roads">{"".join(items)}</div>'

def combo_chart(st, hist):
    """กราฟรายสถานี: ประวัติจริง 60 วัน (เส้น teal) + พยากรณ์ 30 วัน (เส้นส้ม + แถบ lo-hi)
       + เส้นปกติ + เส้นเกณฑ์ + เส้นวันนี้"""
    daily = dict(hist.get("daily", [])) if hist else {}
    series = st.get("series", [])
    if not daily and not series:
        return ""
    W, H, PL, PR, PT, PB = 440, 200, 42, 12, 30, 20
    today = datetime.date.today()
    all_d = sorted(set(list(daily) + [v["d"] for v in series]))
    d0 = datetime.date.fromisoformat(all_d[0])
    d1 = datetime.date.fromisoformat(all_d[-1])
    span = max(1, (d1 - d0).days)

    def xs(dstr):
        return PL + (W - PL - PR) * ((datetime.date.fromisoformat(dstr) - d0).days / span)

    vals = list(daily.values()) + [v["h"] for v in series] + [v["lo"] for v in series] + [v["hi"] for v in series]
    for extra in (st.get("normal"), st.get("ref"), st.get("warn")):
        if extra is not None:
            vals.append(float(extra))
    lo, hi = min(vals), max(vals)
    pad = max(0.08, (hi - lo) * 0.08)
    lo, hi = lo - pad, hi + pad

    def ys(v):
        return PT + (H - PT - PB) * (1 - (v - lo) / (hi - lo))

    def fmt_d(dstr):
        return f"{int(dstr[8:10])}/{int(dstr[5:7])}"

    p = []
    p.append(f'<text x="{PL}" y="14" font-size="12" font-weight="600" fill="#222">{html.escape(st["name"][:34])}</text>')
    cur = f'ตอนนี้ {st["h0"]:.2f}'
    if st.get("normal") is not None:
        cur += f' · ปกติ {st["normal"]:.2f}'
    p.append(f'<text x="{W-PR}" y="14" font-size="10.5" fill="#00838f" text-anchor="end">{cur}</text>')

    # แกน + grid แนวนอน 3 ระดับ
    for frac in (0.0, 0.5, 1.0):
        v = lo + (hi - lo) * frac
        y = ys(v)
        p.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#e3e8ee" stroke-width="1"/>')
        p.append(f'<text x="{PL-4}" y="{y+3.5:.1f}" font-size="9.5" fill="#777" text-anchor="end">{v:.2f}</text>')

    # เส้นเกณฑ์ (แดงประ)
    if st.get("ref"):
        y = ys(float(st["ref"]))
        if PT - 2 <= y <= H - PB + 2:
            p.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#c62828" stroke-width="1.2" stroke-dasharray="5 3"/>')
            p.append(f'<text x="{W-PR}" y="{y-3:.1f}" font-size="9" fill="#c62828" text-anchor="end">เกณฑ์ {st["ref"]:.2f}</text>')
    # เส้นปกติ (ฟ้าประ)
    if st.get("normal") is not None:
        y = ys(float(st["normal"]))
        if PT - 2 <= y <= H - PB + 2:
            p.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#00acc1" stroke-width="1.4" stroke-dasharray="6 3"/>')
            p.append(f'<text x="{PL+3}" y="{y-3:.1f}" font-size="9" fill="#00acc1">ปกติ {st["normal"]:.2f}</text>')
    if st.get("warn") and st.get("warn") != st.get("ref"):
        y = ys(float(st["warn"]))
        if PT - 2 <= y <= H - PB + 2:
            p.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#ef6c00" stroke-width="1.1" stroke-dasharray="3 3"/>')
            p.append(f'<text x="{PL+3}" y="{y-3:.1f}" font-size="9" fill="#ef6c00">เตือนภัย {st["warn"]:.2f}</text>')

    # เส้นวันนี้
    tstr = today.isoformat()
    if d0.isoformat() <= tstr <= d1.isoformat():
        x = xs(tstr)
        p.append(f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{H-PB}" stroke="#666" stroke-width="1" stroke-dasharray="2 3"/>')
        p.append(f'<text x="{x:.1f}" y="{H-PB+11}" font-size="9" fill="#666" text-anchor="middle">วันนี้</text>')

    # ประวัติจริง (teal) — ตัดช่วงขาดเป็น segment
    seg, segs = [], []
    dcur = d0
    while dcur <= today:
        k = dcur.isoformat()
        if k in daily:
            seg.append((xs(k), ys(daily[k])))
        elif seg:
            segs.append(seg); seg = []
        dcur += datetime.timedelta(days=1)
    if seg:
        segs.append(seg)
    for sg in segs:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in sg)
        p.append(f'<polyline points="{pts}" fill="none" stroke="#00838f" stroke-width="2"/>')

    # พยากรณ์: แถบ lo-hi + เส้น h (ส้ม)
    if series:
        fwd = " ".join(f'{xs(v["d"]):.1f},{ys(v["lo"]):.1f}' for v in series)
        bwd = " ".join(f'{xs(v["d"]):.1f},{ys(v["hi"]):.1f}' for v in reversed(series))
        p.append(f'<polygon points="{fwd} {bwd}" fill="#ffb74d" opacity="0.25" stroke="none"/>')
        pts = " ".join(f'{xs(v["d"]):.1f},{ys(v["h"]):.1f}' for v in series)
        p.append(f'<polyline points="{pts}" fill="none" stroke="#ef6c00" stroke-width="2"/>')
        # จุดเชื่อมวันนี้ -> วันแรกของ forecast
        if st["series"]:
            p.append(f'<line x1="{xs(tstr):.1f}" y1="{ys(st["h0"]):.1f}" x2="{xs(series[0]["d"]):.1f}" y2="{ys(series[0]["h"]):.1f}" stroke="#ef6c00" stroke-width="1" stroke-dasharray="2 2" opacity="0.7"/>')

    # ป้ายแกน x
    for lab, anchor in ((fmt_d(all_d[0]), "start"), (fmt_d(all_d[-1]), "end")):
        p.append(f'<text x="{xs(all_d[0] if anchor == "start" else all_d[-1]):.1f}" y="{H-6}" font-size="9" fill="#777" text-anchor="{anchor}">{lab}</text>')

    return (f'<svg viewBox="0 0 {W} {H}" class="chart" style="background:#fff">{"".join(p)}</svg>')

def map_section(sn, normals=None):
    feats = []
    for s in sn["stations"]:
        if s.get("lat") is None or s.get("lon") is None:
            continue
        prov = next((v for k, v in PROVINCE.items() if k in s["name"]), "")
        crit = next((v for k, v in CRITICAL_LOCAL.items() if k in s["name"]), None)
        ref = crit if crit is not None else s["bank"]
        ref_name = "ระดับวิกฤตฝั่งเรา" if crit is not None else "ธงภัย"
        lab, pct = status_label(s["msl"], ref, (normals or {}).get(s["key"]))
        feats.append({"n": s["name"], "p": prov, "r": s["river"], "m": s["msl"],
                      "b": s["bank"], "c": crit, "dt": s.get("dt"),
                      "lab": f"{lab} ({pct:.0f}% ของ{ref_name})",
                      "lat": s["lat"], "lon": s["lon"], "g": s["group"],
                      "col": level_color(s["msl"], ref)})
    data = json.dumps(feats, ensure_ascii=False)
    home = json.dumps(HOME, ensure_ascii=False)
    jdams = json.dumps(sn.get("dams", []), ensure_ascii=False)
    jcanals = json.dumps(sn.get("canals", []), ensure_ascii=False)
    jroads = json.dumps(sn.get("roads", []), ensure_ascii=False)
    return """
<h2>แผนที่สถานีทั้งสายน้ำ + ทางระบายของซอยคุณ</h2>
<div class="panel">
 <div id="map" style="height:540px;border-radius:8px;z-index:0"></div>
 <div class="legend">● สีหมุด = ปกติ (เขียว) / สูง (เหลือง) / ใกล้ธงภัย (ส้ม) / ถึง-ล้นธงภัย (แดง) — คลองฝั่งเราเทียบ "ระดับวิกฤตฝั่งเรา" · เส้นน้ำเงิน = แนวเจ้าพระยา ต้นน้ำ→ปากน้ำ · เส้นประฟ้า = เส้นทางระบายของซอย (บ้าน → คลองสอง → ปากคลองลาดพร้าว/เจ้าพระยา) · 🏠 = บ้านคุณ · กดหมุดเพื่อดูรายละเอียด+จังหวัด+สถานะ<br>แผนที่พื้นหลังโหลดจาก OpenStreetMap ตอนเปิดออนไลน์ (ถ้าออฟไลน์จะเห็นแต่หมุดบนพื้นเทา)</div>
</div>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const F = __DATA__, HOME = __HOME__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 18, attribution: '&copy; OpenStreetMap'}).addTo(map);
const pts = [[HOME.lat, HOME.lon]];
const byGroup = {};
F.forEach(f => {
  pts.push([f.lat, f.lon]);
  (byGroup[f.g] = byGroup[f.g] || []).push(f);
  L.circleMarker([f.lat, f.lon], {radius: 9, color: '#fff', weight: 2, fillColor: f.col, fillOpacity: 0.95})
   .addTo(map)
   .bindPopup('<b>' + f.n + '</b><br>จังหวัด: ' + f.p + '<br>ลำน้ำ: ' + f.r +
              '<br>ระดับ: <b>' + f.m.toFixed(2) + ' ม.</b>' + (f.b ? ' (ธงภัย ' + f.b.toFixed(2) + ' ม.)' : '') +
              '<br>สถานะ: <b>' + f.lab + '</b><br>อ่านล่าสุด: ' + (f.dt || '-'));
});
const chain = (byGroup.upstream || []).concat(byGroup.city || []).sort((a, b) => b.lat - a.lat);
if (chain.length > 1)
  L.polyline(chain.map(f => [f.lat, f.lon]), {color: '#1565c0', weight: 4, opacity: 0.75}).addTo(map)
   .bindTooltip('แนวแม่น้ำเจ้าพระยา ต้นน้ำ → ปากน้ำ');
const drainPts = [[HOME.lat, HOME.lon]];
(byGroup.local || []).forEach(f => drainPts.push([f.lat, f.lon]));
const nul = (byGroup.city || []).find(f => f.n.includes('นวลฉวี'));
if (nul) drainPts.push([nul.lat, nul.lon]);
L.polyline(drainPts, {color: '#00838f', weight: 3, dashArray: '8 8', opacity: 0.9}).addTo(map)
 .bindTooltip('เส้นทางระบายของซอย: บ้าน → คลองสอง → ปากคลองลาดพร้าว (เจ้าพระยา)');
L.circleMarker([HOME.lat, HOME.lon], {radius: 13, color: '#0d47a1', weight: 4, fillColor: '#fff', fillOpacity: 1})
 .addTo(map)
 .bindPopup('<b>' + HOME.name + '</b><br>จุดอ้างอิงพิกัด: 13.9175, 100.6512<br>คลองรอบข้าง: คลองสอง (ผ่านคลองหกวา → ปากคลองลาดพร้าว)');
const DAMS = __DAMS__, CANALS = __CANALS__, ROADS = __ROADS__;
DAMS.forEach(d => {
  if (!d.lat || !d.lon) return;
  pts.push([d.lat, d.lon]);
  const p = d.storage_pct || 0;
  const col = p >= 100 ? '#c62828' : (p >= 85 ? '#f9a825' : '#2e7d32');
  L.circleMarker([d.lat, d.lon], {radius: 13, color: '#000', weight: 2, fillColor: col, fillOpacity: 0.95})
   .addTo(map)
   .bindPopup('<b>เขื่อน' + d.name + '</b><br>กักน้ำ <b>' + p.toFixed(1) + '%</b> ของความจุปกติ (' + (d.storage_mcm||0).toLocaleString() + ' ลม.ม.)' +
              '<br>ไหลเข้า ' + (d.inflow||0) + ' · ใช้/ระบาย ' + (d.released||0) + ' ลม.ม./วัน<br>ข้อมูล: ' + d.date);
});
CANALS.forEach(c => {
  if (!c.lat || !c.lon) return;
  pts.push([c.lat, c.lon]);
  const v = c.value, w = c.warn, k = c.crit;
  let col = '#9e9e9e';
  if (v != null && k) col = v >= k ? '#c62828' : (w && v >= w ? '#f9a825' : '#2e7d32');
  L.circleMarker([c.lat, c.lon], {radius: 6, color: '#fff', weight: 1.5, fillColor: col, fillOpacity: 0.95})
   .addTo(map)
   .bindPopup('<b>' + c.name + '</b> (กทม.)<br>ระดับ: <b>' + (v != null ? v.toFixed(2) : '-') + ' ม.</b>' +
              '<br>เตือนภัย ' + (w ?? '-') + ' · วิกฤต ' + (k ?? '-') +
              '<br>ห่างจากซอย ' + c.dist_km + ' กม.<br>อ่านล่าสุด: ' + c.dt);
});
ROADS.forEach(r => {
  if (!r.lat || !r.lon) return;
  const cm = r.cm || 0;
  const col = cm <= 0.5 ? '#2e7d32' : (cm <= 10 ? '#f9a825' : '#c62828');
  L.circleMarker([r.lat, r.lon], {radius: 5, color: '#333', weight: 1, fillColor: col, fillOpacity: 0.9})
   .addTo(map)
   .bindPopup('<b>' + r.name + '</b><br>น้ำบนถนน: <b>' + (cm <= 0.5 ? 'แห้ง' : cm.toFixed(1) + ' ซม.') + '</b><br>ห่าง ' + r.dist_km + ' กม. · ' + r.dt);
});
map.fitBounds(L.latLngBounds(pts).pad(0.15));
</script>""".replace("__DATA__", data).replace("__HOME__", home).replace("__DAMS__", jdams).replace("__CANALS__", jcanals).replace("__ROADS__", jroads)

def main():
    snaps = load_all()
    sn = snaps[-1]
    first_map = {}
    for s in snaps[0]["stations"]:
        first_map[s["key"]] = s["msl"]
    up = [s for s in sn["stations"] if s["group"] == "upstream"]
    city = [s for s in sn["stations"] if s["group"] == "city"]
    local = [s for s in sn["stations"] if s["group"] == "local"]
    sea = [s for s in sn["stations"] if s["group"] == "sea"]
    head = [s for s in sn["stations"] if s["group"] == "headwater"]
    rap = [s for s in sn["stations"] if s["group"] == "rapipat"]
    dams = sn.get("dams", [])
    canals = sn.get("canals", [])
    roads = sn.get("roads", [])
    lights, verdict = traffic(snaps)
    dot = {"g": ("#2e7d32", "เขียว"), "y": ("#ef6c00", "เหลือง"), "r": ("#c62828", "แดง")}
    cards = "".join(
        f'<div class="card"><div class="dot" style="background:{dot[l][0]}"></div><b>{html.escape(t)}</b><div class="val">{html.escape(v)}</div><div class="rule">{html.escape(r)}</div></div>'
        for l, t, v, r in lights)
    hist = "".join(history_chart(snaps, lbl, key) for lbl, key in
                   [("ปากคลองลาดพร้าว (นวลฉวี)", "นวลฉวี"), ("คลองหกวา ปากคลอง 2", "ปากคลอง2สายใต้"),
                    ("สามเสน", "สามเสน"), ("บางปะอิน", "บางปะอิน")])
    normals, ndays = snapshot_p25(snaps)
    norm_ext, norm_can, norm_built = load_normals_ext()
    try:
        fc = open(os.path.join(BASE, "data", "fc_days.json")).read()
    except FileNotFoundError:
        fc = "null"
    try:
        fc_obj = json.loads(fc)
    except Exception:
        fc_obj = None
    try:
        histd = json.load(open(os.path.join(BASE, "data", "station_history.json")))
    except Exception:
        histd = {"stations": {}, "canals": {}}
    combo = ""
    if fc_obj:
        def find_hist(s):
            key = s.get("key") or ""
            for pool in ("canals", "stations"):     # canal ก่อน (datum ตรงเซ็นเซอร์ กทม.)
                h = histd.get(pool, {})
                if key in h:
                    return h[key]
                for k, v in h.items():
                    if key in k or k in s.get("name", ""):
                        return v
            return None
        combo = "".join(combo_chart(s, find_hist(s)) for s in fc_obj.get("stations", []))
    html_out = f"""<!DOCTYPE html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard น้ำ สายไหม 44</title><style>
 body{{font-family:-apple-system,'Segoe UI','Noto Sans Thai',sans-serif;margin:0;background:#f4f6f8;color:#222}}
 header{{background:#0d47a1;color:#fff;padding:18px 26px}}
 header h1{{margin:0;font-size:22px}} header .sub{{opacity:.85;font-size:13px;margin-top:4px}}
 .verdict{{display:inline-block;margin-top:10px;padding:8px 16px;border-radius:8px;font-weight:700;color:#fff;background:{verdict[1]}}}
 main{{max-width:960px;margin:0 auto;padding:18px}}
 h2{{font-size:17px;border-left:5px solid #0d47a1;padding-left:10px;margin:28px 0 10px}}
 .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}
 .card{{background:#fff;border-radius:10px;padding:12px;box-shadow:0 1px 4px rgba(0,0,0,.08);font-size:13px}}
 .card .val{{font-size:15px;margin:6px 0 4px;font-weight:700}}
 .card .rule{{color:#888;font-size:11px}}
 .dot{{width:22px;height:22px;border-radius:50%;display:inline-block;margin-right:8px;vertical-align:middle;box-shadow:inset 0 -2px 4px rgba(0,0,0,.2)}}
 .panel{{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .row{{display:grid;grid-template-columns:250px 1fr 150px;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid #eee}}
 .row:last-child{{border-bottom:0}}
 .rname{{font-size:13px;font-weight:600}} .river{{display:block;color:#999;font-weight:400;font-size:11px}}
 .track{{position:relative;height:16px;background:#e3e8ee;border-radius:8px;overflow:visible}}
 .fill{{height:100%;border-radius:8px;min-width:4px}}
 .bankmark{{position:absolute;right:0;top:-3px;bottom:-3px;width:3px;background:#333;border-radius:2px}}
 .normmark{{position:absolute;top:-4px;bottom:-4px;width:3px;background:#00acc1;border-radius:2px;z-index:2;box-shadow:0 0 0 1px rgba(255,255,255,.6)}}
 .rmeta{{font-size:11.5px;color:#555;margin-top:3px}}
 .rtrend{{font-size:12.5px;font-weight:700;text-align:right}} .since{{display:block;font-weight:400;font-size:10.5px;color:#999}}
 .chart{{width:100%;height:auto;background:#fff}} .cap{{color:#777;font-size:11.5px;margin:4px 0 0}}
 .hint{{color:#999;font-size:12.5px}}
 .legend{{font-size:11.5px;color:#666;margin-top:8px}} .legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}}
 .roads{{display:flex;flex-wrap:wrap;gap:8px}} .roadchip{{border:2px solid;border-radius:14px;padding:4px 10px;font-size:12px;background:#fff}}
 .tabs{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}}
 .tab{{padding:7px 14px;border-radius:8px;border:1.5px solid #b9c6d6;background:#fff;font-size:13px;cursor:pointer;font-weight:600;color:#33465e}}
 .tab.active{{background:#0d47a1;color:#fff;border-color:#0d47a1}}
 .fcrow{{display:grid;grid-template-columns:230px 1fr 190px;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid #eee}}
 .fcband{{font-size:10.5px;color:#999}}
 .note{{font-size:11.5px;color:#777;background:#f0f4f8;border-radius:8px;padding:10px 12px;margin-top:10px;line-height:1.6}}
 footer{{color:#888;font-size:11.5px;padding:20px 26px;max-width:960px;margin:0 auto}}
 @media(max-width:720px){{.row{{grid-template-columns:150px 1fr}} .rtrend{{grid-column:2}}}}
</style></head><body>
<header>
 <h1>Dashboard น้ำท่วม — ท้ายซอยสายไหม 44 เขตสายไหม กรุงเทพฯ</h1>
 <div class="sub">ติดตามครบสายน้ำ: เขื่อนเจ้าพระยา → อยุธยา → บางปะอิน → กรุงเทพฯ → ปากน้ำออกทะเล | อัปเดตล่าสุด: {sn['fetched_at']} | snapshots สะสมแล้ว {len(snaps)} ครั้ง</div>
 <div class="verdict">สรุปวันนี้: {verdict[0]}</div>
</header>
<main>
 <h2>ไฟจราจรประเมินรายวัน (ดูทุกเช้า)</h2>
 <div class="cards">{cards}</div>
 <div class="legend">เขียว = ปัจจัยเป็นใจให้น้ำลด · เหลือง = เฉื่อย · แดง = ยังกั้นการระบาย — เมื่อ 5 ใน 7 ดวงเขียว น้ำหน้าบ้านจะลดชัด (ดวงที่ 6–7 คือฝนภาคเหนือกับเขื่อน = มวลน้ำรอบใหม่)</div>

 <h2>ต้นน้ำภาคเหนือ (ปิง–น่าน–ยม) + เขื่อน + คลองระพีพัฒน์</h2>
 <div class="panel">{station_rows(head, first_map, normals, norm_ext)}
 <div class="legend">ฝน/น้ำหลากที่สถานีเหล่านี้วันนี้ = ระดับเจ้าพระยาที่กรุงเทพฯ ในอีก ~3–7 วัน</div></div>
 <div class="panel" style="margin-top:10px">{dam_rows(dams)}
 <div class="legend">เขื่อน ≥100% ความจุปกติ = ต้องระบายเพิ่ม = มวลน้ำใหม่เดินมากรุงเทพฯ (ข้อมูล กฟผ./กรมชลฯ ผ่าน thaiwater)</div></div>
 <div class="panel" style="margin-top:10px">{station_rows(rap, first_map, normals, norm_ext)}
 <div class="legend">คลองระพีพัฒน์ = "ประตูหลัง" ที่น้ำเจ้าพระยาแยกเข้าคลองหกวา–ลำลูกกา มาถึงซอยคุณโดยไม่ผ่านปากคลองลาดพร้าว</div></div>

 <h2>แนวน้ำเจ้าพระยา: ต้นน้ำ → กรุงเทพฯ (เรียงเหนือ→ใต้)</h2>
 <div class="panel">{station_rows(up + city, first_map, normals, norm_ext)}
 <div class="legend"><i style="background:#2e7d32"></i>ปกติ (&lt;70% ของธงภัย) <i style="background:#f9a825"></i>สูง (70–85%) <i style="background:#ef6c00"></i>ใกล้ธงภัย (85–100%) <i style="background:#c62828"></i>ถึง/ล้นธงภัย · ▲▼ = เทียบอ่านก่อนหน้า (~1–3 ชม.) · เส้นดำขวาสุด = ธงภัย (bank) · <i style="background:#00acc1"></i>เส้นฟ้า = ระดับน้ำปกติ (median ประวัติ 60 วัน ตัดช่วงเหตุการณ์ — คำนวณล่าสุด {norm_built[:16] if norm_built else '—'}; สถานีที่ไม่มีเส้น = ยังไม่มีข้อมูลประวัติ จะสะสมเองจาก snapshot เมื่อครบ 14 วัน){'<br>เกณฑ์ "ปกติ" ชั่วคราวใช้ % ของธงภัย (API ไม่มีค่าเฉลี่ยรายสถานี) — สะสมแล้ว ' + str(ndays) + '/14 วัน เมื่อครบระบบจะใช้ค่าปกติจริงจากประวัติสถานีอัตโนมัติ' if not normals else '<br>ค่าปกติอ้างอิง percentile 25 จากประวัติ ' + str(ndays) + ' วันของสถานี'}</div></div>

 <h2>คลองพื้นที่เรา + ปากน้ำฝั่งทะเล</h2>
 <div class="panel">{station_rows(local + sea, first_map, normals, norm_ext)}
 <div class="legend">คลองฝั่งเราใช้ "ระดับวิกฤตฝั่งเรา" แทนธงภัยทางการ (ธงภัยคลองหกวา 4.46 ม. สูงเกินจริงเทียบระดับที่น้ำเข้าซอย) · ปากคลองพระองค์เจ้า + คลองลัดบางยอ = ตัวแทน "น้ำหนุนทะเล" — ถ้าค่าขึ้นลงตามวัฏจักรราย 6 ชม. แปลว่าน้ำหนุนกำลังอัดปากคลอง</div></div>

 <h2>เซ็นเซอร์ทางการ กทม. รอบซอย (อัปเดตราย 10–15 นาที)</h2>
 <div class="panel">{canal_rows(canals)}
 <div class="legend">เกณฑ์เตือนภัย/วิกฤตเป็นค่าทางการของสำนักการระบายน้ำ กทม. — "ปตร.คลองสองสายใต้" (ห่างซอย ~2 กม.) ใช้กรอบอ้างอิงต่างจากสถานีกรมชลประทาน อ่านคู่กันได้ · <i style="background:#00acc1"></i>เส้นฟ้า = ระดับปกติ (ไม่ท่วม) ตามเกณฑ์เตือนภัย กทม. — ต่ำกว่าเส้นนี้ = น้ำในซอยไม่ท่วม</div></div>
 <div class="panel" style="margin-top:10px">{road_rows(roads)}
 <div class="legend">เซ็นเซอร์วัดความลึกน้ำบนผิวถนน (ซม.) ในรัศมี 7.5 กม. จากซอย — สีเขียว=แห้ง เหลือง≤10 ซม. แดง>10 ซม.</div></div>
{map_section(sn, normals)}

 <h2>ฝนที่ตัวซอย 44 (ย้อนหลัง 7 วัน + พยากรณ์ 16 วัน)</h2>
 <div class="panel">{rain_chart(sn['wx_daily'])}
 <div class="legend"><i style="background:#1565c0"></i>ย้อนหลัง <i style="background:#90caf9"></i>พยากรณ์ (มม./วัน)</div></div>

 <h2>ประวัติระดับน้ำรายวัน (สะสมจาก snapshot รายชั่วโมง)</h2>
 <div class="panel" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px">{hist}</div>

 <h2>Forecast รายวัน 30 วัน — เลือกวันที่ดูการทำนายระดับน้ำ (กรอบวันที่ขีดเส้นประ = คาดหมายฤดูกาล)</h2>
 <div class="panel">
  <div class="tabs" id="fcTabs"></div>
  <div id="fcBody"></div>
  <div class="note" id="fcNote"></div>
 </div>

 <h2>ประวัติจริง 60 วัน + พยากรณ์ 30 วัน รายสถานี — เทียบระดับปกติด้วยตา</h2>
 <div class="panel" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px">{combo}</div>
 <div class="legend">เส้น teal = ข้อมูลจริงย้อนหลัง 60 วัน (ค่าเฉลี่ยรายวัน จาก thaiwater) · เส้นส้ม = พยากรณ์ (แถบอ่อน = ช่วงคาด lo–hi) · เส้นประฟ้า = ระดับปกติ (median ก่อนเหตุการณ์) · เส้นประแดง = เกณฑ์ · แนวตั้งเทา = วันนี้ · ข้อมูลย้อนหลังรีเฟรชทุก 24 ชม.</div>
</main>
<footer>
 แหล่งข้อมูล: ระดับน้ำ = api-v3.thaiwater.net (กรมชลประทาน/HII) · ฝน = Open-Meteo · เกณฑ์ไฟจราจรครอบคลุม ฝน-เจ้าพระยา-คลองรับ-มวลน้ำเหนือ-น้ำหนุน-ฝนเหนือ-เขื่อน<br>
 เส้นฟ้าบนหลอด = ระดับน้ำปกติ (median ประวัติ 60 วันจริงจาก thaiwater ตัด 7 วันช่วงเหตุการณ์ — ครบทั้งสถานีกรมชลฯ และเซ็นเซอร์ กทม.) · เซ็นเซอร์ กทม. แสดงเพิ่มเกณฑ์เตือนภัย (ต่ำกว่านี้ = น้ำไม่ท่วมซอย) · รีเฟรชอัตโนมัติทุก 24 ชม.<br>
 อัปเดตอัตโนมัติทุกชั่วโมงโดย cron → <code>python3 scripts/fetch_snapshot.py && python3 scripts/forecast_days.py && python3 scripts/build_dashboard.py</code> แล้วเปิดไฟล์นี้ใหม่ (refresh)
</footer>
<script>
const FC = __FC__;
(function() {{
  if (!FC || !FC.dates || !FC.dates.length) return;
  const tabs = document.getElementById('fcTabs'), body = document.getElementById('fcBody'), note = document.getElementById('fcNote');
  const colOf = (h, ref) => h >= ref ? '#c62828' : (h >= ref*0.85 ? '#ef6c00' : (h >= ref*0.7 ? '#f9a825' : '#2e7d32'));
  const labOf = (h, ref) => h >= ref ? 'ถึง/ล้นเกณฑ์' : (h >= ref*0.85 ? 'ใกล้เกณฑ์' : (h >= ref*0.7 ? 'สูง' : 'ปกติ'));
  function render(di) {{
    const d = FC.dates[di];
    const sv = FC.stations[0].series[di];
    const tierTxt = sv.tier === 2 ? ' <span style="font-weight:400;font-size:12px;color:#888">· ช่วงคาดหมายฤดูกาล (SEAS5) — อ่านเป็นภาพรวม ไม่ใช่ค่ารายวัน</span>' : '';
    let html = '<div style="font-weight:700;margin:2px 0 4px">การทำนายวันที่ ' + d.slice(8,10) + '/' + d.slice(5,7) + '/' + (+d.slice(0,4)+543) + ' (ระดับ ม. MSL)' + tierTxt + '</div>'
             + '<div style="font-size:12px;color:#666;margin:0 0 8px">ฝนที่ซอยคาด ~' + sv.rain + ' มม. · ตัวคูณน้ำหนุน (การระบาย) ' + sv.tide + ' — ยิ่งต่ำ = น้ำหนุนยิ่งอัด</div>';
    FC.stations.forEach(s => {{
      const v = s.series[di];
      const pct = Math.min(100, v.h / s.ref * 100);
      const col = colOf(v.h, s.ref);
      const delta = (v.h - s.h0) * 100;
      const dTxt = delta >= 1 ? '▲ +' + delta.toFixed(0) + ' ซม. จากวันนี้' : (delta <= -1 ? '▼ ' + delta.toFixed(0) + ' ซม. จากวันนี้' : '≈ คงที่');
      const nrmTxt = s.normal != null ? ' · <span style="color:#00838f">ปกติ ~' + s.normal.toFixed(2) + ' ม.</span>' : '';
      let nrmDate = '';
      if (s.normal != null || s.warn != null) {{
        const MON = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
        const okLab = (s.grp === 'canal' && s.warn != null) ? 'น้ำไม่ท่วมซอย' : 'กลับปกติ';
        const bd = s.back_ok || s.back_normal;
        if (bd) {{
          const passed = FC.dates.indexOf(bd) <= di;
          nrmDate = '<span class="fcband" style="color:' + (passed ? '#2e7d32' : '#00838f') + '">' +
                    (passed ? '✓ ' + okLab + 'แล้ว (~' : 'คาด' + okLab + ' ~') +
                    (+bd.slice(8,10)) + ' ' + MON[+bd.slice(5,7)-1] + ')</span>';
        }} else {{
          nrmDate = '<span class="fcband" style="color:#ef6c00">ยังเกินปกติทั้ง 30 วัน</span>';
        }}
      }}
      const normPos = s.normal != null ? Math.min(99.5, s.normal / s.ref * 100) : null;
      const normMark = normPos != null ? '<div class="normmark" style="left:' + normPos.toFixed(1) + '%"></div>' : '';
      html += '<div class="fcrow"><div class="rname">' + s.name + '<span class="fcband">ตอนนี้ ' + s.h0.toFixed(2) + ' ม.</span></div>'
            + '<div class="rbar"><div class="track"><div class="fill" style="width:' + pct.toFixed(1) + '%;background:' + col + '"></div>' + normMark + '<div class="bankmark"></div></div>'
            + '<div class="rmeta"><b>' + v.h.toFixed(2) + ' ม.</b> (ช่วงคาด ' + v.lo.toFixed(2) + '–' + v.hi.toFixed(2) + ') = ' + (v.h/s.ref*100).toFixed(0) + '% ของเกณฑ์ ' + s.ref.toFixed(2) + nrmTxt + ' — <b>' + labOf(v.h, s.ref) + '</b></div></div>'
            + '<div class="rtrend" style="color:' + (delta >= 1 ? '#c62828' : delta <= -1 ? '#2e7d32' : '#666') + '">' + dTxt + (nrmDate ? '<br>' + nrmDate : '') + '</div></div>';
    }});
    body.innerHTML = html;
    note.innerHTML = '<b>วิธีคำนวณ:</b> ' + FC.note + '<br><b>อินพุตวันนี้:</b> บางปะอินสูงเหนือตลิ่ง ' + (FC.bpa_excess*100).toFixed(0) + ' ซม. · อัตราไหลขึ้นบางปะอิน ' + (FC.v_bpa*100).toFixed(0) + ' ซม./วัน · ฝนเหนือต่อวัน (ค่าเฉลี่ย 4 จุด): ' + Object.entries(FC.north_by_day).slice(1).map(([k,v]) => k.slice(8,10) + '/' + k.slice(5,7) + ' = ' + v.toFixed(0) + ' มม.').join(', ');
  }}
  FC.dates.forEach((d, i) => {{
    const b = document.createElement('button');
    b.className = 'tab'; b.textContent = (+d.slice(8,10)) + ' ' + ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'][+d.slice(5,7)-1];
    if (FC.stations[0].series[i].tier === 2) {{ b.style.borderStyle = 'dashed'; b.title = 'คาดหมายฤดูกาล (SEAS5)'; }}
    b.onclick = () => {{ document.querySelectorAll('.tab').forEach(t => t.classList.remove('active')); b.classList.add('active'); render(i); }};
    tabs.appendChild(b);
  }});
  tabs.firstChild.classList.add('active');
  render(0);
}})();
</script></body></html>"""
    out = os.path.join(BASE, "dashboard.html")
    open(out, "w").write(html_out.replace("__FC__", fc))
    print("OK", out)

if __name__ == "__main__":
    main()
