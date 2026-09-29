#!/usr/bin/env python3
"""ดึงสถานะเขื่อนใหญ่ทั่วประเทศจาก 3 แหล่ง แล้วเทียบกันเอง -> data/dams_verified.json
   + สะสมประวัติรายวันจาก RID -> data/dam_history.json

แหล่งข้อมูล (verify แล้ว Sep 29, 2026):
  RID     app.rid.go.th/reservoir/api/dam/public[/YYYY-MM-DD]  กรมชลประทาน (ต้นทาง) 35 เขื่อน
          ย้อนหลังรายวันได้ ใช้ backfill ประวัติ + เทียบปีที่แล้ว
  HII     api-v3.thaiwater.net/.../analyst/dam  สสน. (ตัวรวบรวม) แถว RID + แถว EGAT
  EGAT    water.egat.co.th/daily_infographic.php  กฟผ. (ต้นทาง) 11 เขื่อนผลิตไฟฟ้า
          มีเกณฑ์ rule curve บน/ล่าง ซึ่งอีกสองแหล่งไม่มี

ความหมาย field (ทุกแหล่งใช้ฐานเดียวกัน):
  pct       = ปริมาตรปัจจุบัน / ความจุที่ระดับเก็บกักปกติ (รนก.) x 100 เกิน 100 ได้
  volume    = ปริมาตรน้ำในอ่างทั้งหมด (ล้าน ลบ.ม.) รวม dead storage
  active    = น้ำใช้การได้ = volume - dead storage  (thaiwater เรียก dam_uses_water)
  inflow/outflow = ล้าน ลบ.ม./วัน"""
import json, os, re, datetime, urllib.request, ssl, html
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "dams_verified.json")
HIST = os.path.join(BASE, "data", "dam_history.json")
HIST_DAYS = 120
UA = {"User-Agent": "saimai-flood-dashboard/1.0"}
CTX = ssl.create_default_context()

EGAT_CODES = {"BB": "ภูมิพล", "SK": "สิริกิติ์", "VRK": "วชิราลงกรณ", "SNR": "ศรีนครินทร์",
              "UR": "อุบลรัตน์", "NP": "น้ำพุง", "SRD": "สิรินธร", "HK": "ห้วยกุ่ม",
              "CLB": "จุฬาภรณ์", "RPB": "รัชชประภา", "BLG": "บางลาง"}


def get(url, as_json=True):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        raw = r.read()
    return json.loads(raw) if as_json else raw.decode("utf-8", "ignore")


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def clean(name):
    return (name or "").replace("เขื่อน", "").replace("อ่างเก็บน้ำ", "").strip()


# ---------- RID ----------
def rid_day(date=None):
    url = "https://app.rid.go.th/reservoir/api/dam/public" + (f"/{date}" if date else "")
    d = get(url)
    rows = {}
    for reg in d.get("data", []):
        for x in reg.get("dam", []):
            rows[clean(x["name"])] = {
                "region": reg.get("region"), "owner": x.get("owner"),
                "capacity": fnum(x.get("capacity")), "normal": fnum(x.get("storage")),
                "dead": fnum(x.get("dead_storage")), "volume": fnum(x.get("volume")),
                "pct": fnum(x.get("percent_storage")), "inflow": fnum(x.get("inflow")),
                "outflow": fnum(x.get("outflow"))}
    return d.get("date"), rows


# ---------- thaiwater (HII) ----------
def hii():
    dd = get("https://api-v3.thaiwater.net/api/v1/thaiwater30/analyst/dam")["data"]
    rows = {}
    for x in dd.get("dam_daily", []):
        m = x.get("dam") or {}
        nm = clean((m.get("dam_name") or {}).get("th"))
        agency = ((x.get("agency") or {}).get("agency_shortname") or {}).get("en", "")
        vol, normal = fnum(x.get("dam_storage")), fnum(m.get("normal_storage"))
        pct = fnum(x.get("dam_storage_percent"))
        # แถว EGAT บางแถวส่ง % = 0 ทั้งที่มีปริมาตร: คำนวณใหม่จากปริมาตร/รนก.
        if (not pct) and vol and normal:
            pct = round(vol / normal * 100, 2)
        rec = {"agency": agency, "date": x.get("dam_date"), "volume": vol, "normal": normal,
               "capacity": fnum(m.get("max_storage")), "pct": pct,
               "active": fnum(x.get("dam_uses_water")),
               "inflow": fnum(x.get("dam_inflow")), "outflow": fnum(x.get("dam_released")),
               "spill": fnum(x.get("dam_spilled")),
               "basin": ((x.get("basin") or {}).get("basin_name") or {}).get("th", ""),
               "province": ((x.get("geocode") or {}).get("province_name") or {}).get("th", ""),
               "lat": fnum(m.get("dam_lat")), "lon": fnum(m.get("dam_long"))}
        # inflow ของแถว EGAT บางตัวเพี้ยน (เช่น แม่งัด 28404) ตัดทิ้งถ้าเกินความจุทั้งอ่าง
        if rec["inflow"] and rec["capacity"] and rec["inflow"] > rec["capacity"]:
            rec["inflow"] = None
        old = rows.get(nm)
        # ชื่อซ้ำ: เลือกแถว RID ก่อน (สดกว่า) ถ้าไม่มีเอาวันที่ใหม่สุด
        if old is None or (agency == "RID" and old["agency"] != "RID") or \
                (agency == old["agency"] and str(rec["date"]) > str(old["date"])):
            rows[nm] = rec
    return rows


# ---------- EGAT ----------
def egat():
    t = get("https://water.egat.co.th/daily_infographic.php", as_json=False)
    rows = {}
    pat = re.compile(r'render_mychart\("[^"]+","(\w+)","([\d.]+)","([\d.]+)","([\d.]+)","([\d.]+)"\);'
                     r'(.*?)(?=render_mychart|$)', re.S)
    for code, pct, dead, lower, upper, tail in pat.findall(t):
        nm = EGAT_CODES.get(code)
        if not nm:
            continue
        txt = html.unescape(re.sub(r"<[^>]+>", " ", tail))
        m = re.search(r"([\d,]+(?:\.\d+)?)", txt)
        rows[nm] = {"code": code, "pct": fnum(pct), "volume": fnum(m.group(1).replace(",", "")) if m else None,
                    "lrc_pct": fnum(lower), "urc_pct": fnum(upper), "dead_pct": fnum(dead)}
    m = re.search(r"วันที่\s*(\d+)\s*(\S+)\s*(\d{4})", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    return (" ".join(m.groups()) if m else None), rows


def match(name, rows):
    if name in rows:
        return rows[name]
    for k, v in rows.items():
        if k and (k in name or name in k):
            return v
    return None


# ---------- run ----------
errors = {}
try:
    rid_date, rid = rid_day()
except Exception as e:
    rid_date, rid = None, {}
    errors["RID"] = str(e)
try:
    hi = hii()
except Exception as e:
    hi = {}
    errors["HII"] = str(e)
try:
    egat_date, eg = egat()
except Exception as e:
    egat_date, eg = None, {}
    errors["EGAT"] = str(e)

# ---------- ประวัติรายวันจาก RID ----------
hist = json.load(open(HIST)) if os.path.exists(HIST) else {}
today = datetime.date.today()
want = [(today - datetime.timedelta(days=i)).isoformat() for i in range(HIST_DAYS)]
# ช่วงเดียวกันของปีที่แล้ว (ย้อน 120 วัน + ล่วงหน้า 60 วัน) ไว้เทียบ
ly = today.replace(year=today.year - 1)
want += [(ly + datetime.timedelta(days=i)).isoformat() for i in range(-HIST_DAYS, 61)]
# วันล่าสุด 3 วันดึงซ้ำเสมอ เผื่อ RID แก้ย้อนหลัง
need = [d for d in want if d not in hist or d >= (today - datetime.timedelta(days=3)).isoformat()]


def fetch_hist(d):
    try:
        got, rows = rid_day(d)
        if got != d or not rows:
            return d, None
        return d, {k: [v["pct"], v["volume"], v["inflow"], v["outflow"]] for k, v in rows.items()}
    except Exception:
        return d, None


with ThreadPoolExecutor(max_workers=6) as ex:
    for d, rows in ex.map(fetch_hist, need):
        if rows:
            hist[d] = rows
keep = set(want)
hist = {d: hist[d] for d in sorted(hist) if d in keep}
json.dump(hist, open(HIST, "w"), ensure_ascii=False, separators=(",", ":"))


# ---------- รวม + เทียบ ----------
def agree(a, b, tol_pct=1.5):
    """ถือว่าตรงกันถ้าต่างไม่เกิน 1.5% ของค่า หรือ 0.5 ล้าน ลบ.ม. (เขื่อนเล็ก)"""
    if a is None or b is None:
        return None
    return abs(a - b) <= max(0.5, abs(b) * tol_pct / 100)


names = list(dict.fromkeys(list(rid) + list(hi) + list(eg)))
dams = []
for nm in names:
    r, h, e = rid.get(nm), match(nm, hi), match(nm, eg)
    # ชื่อสั้นที่เป็นแถวซ้ำของเขื่อนที่มีอยู่แล้ว (เช่น แม่งัด ↔ แม่งัดสมบูรณ์ชล) ข้าม
    if nm not in rid and any(nm != k and nm in k for k in rid):
        continue
    if nm not in rid and nm not in hi and nm not in eg:
        continue
    srcs = {}
    if r:
        srcs["RID"] = {"date": rid_date, "volume": r["volume"], "pct": r["pct"],
                       "inflow": r["inflow"], "outflow": r["outflow"]}
    if h:
        srcs["HII"] = {"date": h["date"], "volume": h["volume"], "pct": h["pct"],
                       "inflow": h["inflow"], "outflow": h["outflow"], "agency": h["agency"]}
    if e:
        srcs["EGAT"] = {"date": egat_date, "volume": e["volume"], "pct": e["pct"]}
    primary = "RID" if r else ("EGAT" if e else "HII")
    p = srcs[primary]
    # ค่าไหลเข้า/ออกใช้ RID ก่อน ถ้าไม่มีใช้ HII
    flow = r or h or {}
    vols = {k: v["volume"] for k, v in srcs.items() if v.get("volume") is not None}
    checks = {k: agree(v, p["volume"]) for k, v in vols.items() if k != primary}
    if not checks:
        verdict = "single"
    elif all(checks.values()):
        verdict = "agree"
    else:
        verdict = "differ"
    normal = (r or {}).get("normal") or (h or {}).get("normal")
    dead = (r or {}).get("dead")
    if dead is None and h and h.get("volume") is not None and h.get("active") is not None:
        dead = round(h["volume"] - h["active"], 2)
    vol = p["volume"]
    pct = p["pct"]
    if pct is None and vol is not None and normal:
        pct = round(vol / normal * 100, 2)
    run_of_river = bool(h and not vol and not (r or e))
    dams.append({
        "name": nm, "region": (r or {}).get("region"),
        "owner": (r or {}).get("owner") or (h or {}).get("agency"),
        "basin": (h or {}).get("basin", ""), "province": (h or {}).get("province", ""),
        "lat": (h or {}).get("lat"), "lon": (h or {}).get("lon"),
        "normal": normal, "capacity": (r or {}).get("capacity") or (h or {}).get("capacity"),
        "dead": dead, "volume": vol, "pct": pct,
        "active": round(vol - dead, 2) if vol is not None and dead is not None else None,
        "room": round(normal - vol, 2) if vol is not None and normal else None,
        "inflow": flow.get("inflow"), "outflow": flow.get("outflow"),
        "spill": (h or {}).get("spill"),
        "urc_pct": (e or {}).get("urc_pct"), "lrc_pct": (e or {}).get("lrc_pct"),
        "run_of_river": run_of_river,
        "primary": primary, "sources": srcs, "checks": checks, "verdict": verdict})

res = {"fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
       "rid_date": rid_date, "egat_date": egat_date, "errors": errors, "dams": dams}
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
v = [d["verdict"] for d in dams]
print(f"OK {OUT} dams={len(dams)} agree={v.count('agree')} differ={v.count('differ')} "
      f"single={v.count('single')} hist_days={len(hist)} errors={errors or '-'}")
for d in dams:
    if d["verdict"] == "differ":
        print("  DIFFER", d["name"], {k: s.get("volume") for k, s in d["sources"].items()})
