#!/usr/bin/env python3
"""คำนวณ "ระดับน้ำปกติ" + เก็บประวัติระดับน้ำรายวัน ย้อนหลัง 60 วัน
   ของทุกสถานี (สถานีกรมชลฯ ผ่าน station_type=tele_waterlevel · เซ็นเซอร์ กทม. ผ่าน tele_canal)

   - ระดับปกติ = median ของค่าเฉลี่ยรายวัน ช่วง [วันนี้−60, วันนี้−7] (ตัดช่วงเหตุการณ์ออก)
   - ค่า graph ของสถานีกรมชลฯ เป็น gauge ของสถานี → แปลงเป็น MSL ด้วย offset จากค่าอ่านล่าสุด
   - เซ็นเซอร์ กทม. ใช้ datum เดียวกับค่า value/warn/crit ที่หน้าเว็บ (ไม่ต้องแปลง MSL)
   - เขียน 2 ไฟล์: data/normal_levels.json (เกณฑ์ปกติ) + data/station_history.json (ประวัติรายวัน ไว้วาดกราฟ)
   รันใหม่อัตโนมัติเมื่ออายุเกิน 24 ชม. โดย fetch_snapshot.py"""
import json, glob, os, datetime, time, urllib.request, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAIN = {
    "headwater": ["เชียงดาว", "สะพานนวรัท", "อ.เมืองน่าน", "เมืองแพร่", "สวรรคโลก",
                  "วัดเกยไชยเหนือ", "ชุมแสงสงคราม"],
    "upstream": ["สะพานเดชาติวงศ์", "ค่ายจิรประวัติ", "สะพานธรรมจักร", "ท้ายเขื่อนเจ้าพระยา",
                 "สรรพยา", "พรหมบุรี", "เมืองอ่างทอง", "บ้านบางแก้ว", "พระนครศรีอยุธยา",
                 "บ้านป้อม", "บางปะอิน"],
    "city": ["กรมชลประทานสามเสน", "สะพานกรุงเทพ", "สะพานนวลฉวี"],
    "local": ["คลองลาดพร้าว ปากคลอง2สายใต้", "คลองลาดพร้าว ท้ายปตร.คลอง2",
              "คลองเปรมประชากร หลักหก", "คลองหกวา ลำลูกกา คลอง8"],
    "rapipat": ["คลองระพีพัฒน์แยกตก", "คลองระพีพัฒน์แยกใต้"],
    "sea": ["ปากคลองพระองค์เจ้า", "คลองลัดบางยอ 1"],
}
WANT = {n: grp for grp, names in CHAIN.items() for n in names}

DAYS_BACK = 60
DAYS_TRIM = 7       # ตัด N วันล่าสุดออกจากการคำนวณ "ปกติ"
MIN_DAYS = 20
GRAPH_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_graph"

def get(url, retry=3, sleep=4):
    for i in range(retry + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "saimai-flood-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception:
            if i == retry:
                raise
            time.sleep(sleep)

def parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(str(s)[:19], fmt)
        except ValueError:
            continue
    return None

def graph_daily(station_id, station_type, start, end, t0=None, val_now=None):
    """ดึง graph 60 วัน → (daily_mean รายวันใน datum ของ graph, offset ไปยังค่าอ่านจริง)
       t0/val_now = เวลา+ค่าอ่านล่าสุดของสถานี ใช้หา offset"""
    g = get(f"{GRAPH_URL}?station_type={station_type}&station_id={station_id}"
            f"&start_date={start}&end_date={end}")["data"]["graph_data"]
    if len(g) < 200:
        raise ValueError(f"ข้อมูลน้อยเกินไป ({len(g)} จุด)")

    offset = 0.0
    if t0 is not None and val_now is not None:
        best, bestgap = None, None
        for pt in g[-500:]:
            t = parse_dt(pt["datetime"])
            if t is None or pt.get("value") is None:
                continue
            gap = abs((t - t0).total_seconds())
            if bestgap is None or gap < bestgap:
                best, bestgap = pt["value"], gap
        if best is None or bestgap > 6 * 3600:
            raise ValueError("หาค่า graph ตรงเวลาค่าอ่านไม่ได้")
        offset = val_now - float(best)

    per_day = {}
    for pt in g:
        t = parse_dt(pt["datetime"])
        if t and pt.get("value") is not None:
            per_day.setdefault(t.date().isoformat(), []).append(float(pt["value"]) + offset)
    # ตัดค่าฟิสิกส์เป็นไปไม่ได้ออก (เช่น เซ็นเซอร์ชำรุดส่ง -2.01 — ระดับคลอง/แม่น้ำระบบนี้ไม่ต่ำกว่า -1.5 ม.)
    daily = {d: sum(v) / len(v) for d, v in per_day.items()
             if len(v) >= 6 and sum(v) / len(v) >= -1.5}
    return daily, offset

def sane_normal(pre_daily, ref_val, fallback=None):
    """normal จาก median + guard: เทียบกับค่าต้นสุดของประวัติ (ยุคก่อนเหตุการณ์)
       - ห่าง > 1.5 ม. (ระดับขึ้นตามฤดูกาล) → ใช้ค่ายุคต้นเป็น normal (source=oldest10)
       - ถ้ามี fallback (เช่น เกณฑ์เตือนภัย กทม.) ใช้ fallback ก่อน oldest10"""
    if len(pre_daily) < MIN_DAYS:
        return (round(fallback, 2) if fallback is not None else None), "bma_warn" if fallback is not None else None
    n = statistics.median(pre_daily.values())
    if ref_val is not None and abs(n - ref_val) > 1.5:
        if fallback is not None:
            return round(fallback, 2), "bma_warn"
        if ref_val is not None:
            return round(ref_val, 2), "oldest10"
    return round(n, 2), "graph60d"

def oldest_median(daily, n=10):
    """median ของ n วันแรกสุดของประวัติ — ใช้เป็นค่าอ้างอิงยุคก่อนเหตุการณ์"""
    first = sorted(daily.items())[:n]
    return statistics.median([v for _, v in first]) if first else None

def main():
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=DAYS_BACK)).isoformat()
    end = today.isoformat()
    cut = today - datetime.timedelta(days=DAYS_TRIM)

    # 1) สถานีกรมชลฯ: id + ค่าอ่านล่าสุด
    rows = {}
    for s in get("https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load")["waterlevel_data"]["data"]:
        st = s.get("station") or {}
        name = (st.get("tele_station_name") or {}).get("th", "")
        for key in WANT:
            if key in name:
                try:
                    msl = float(s.get("waterlevel_msl"))
                except (TypeError, ValueError):
                    break
                rows[key] = {"id": st.get("id"), "name": name.strip(), "msl": msl,
                             "dt": s.get("waterlevel_datetime")}
                break
    print(f"matched {len(rows)}/{len(WANT)} stations from waterlevel_load")

    out, history = {}, {}
    for key, r in sorted(rows.items()):
        if not r["id"]:
            continue
        try:
            daily, offset = graph_daily(r["id"], "tele_waterlevel", start, end,
                                        parse_dt(r["dt"]), r["msl"])
        except Exception as e:
            print(f"WARN {key}: {e}")
            continue
        time.sleep(1.2)
        pre = {d: v for d, v in daily.items() if datetime.date.fromisoformat(d) < cut}
        normal, src = sane_normal(pre, oldest_median(daily))
        if len(pre) < MIN_DAYS:
            print(f"WARN {key}: มีข้อมูลก่อนเหตุการณ์แค่ {len(pre)} วัน (<{MIN_DAYS}) — เก็บ history แต่ไม่คำนวณปกติ")
        out[key] = {"id": r["id"], "normal": normal, "n_days": len(pre),
                    "source": src if (normal is not None or src) else "nodata",
                    "offset": round(offset, 2)}
        # ตัดค่าชำรุด (ห่างค่าปัจจุบัน > 2.8 ม. เช่น -2.01 จากเซ็นเซอร์พัง) ออกจากประวัติก่อนเก็บ
        clean = {d: v for d, v in daily.items() if abs(v - r["msl"]) <= 2.8}
        history[key] = {"name": r["name"], "normal": normal, "daily": sorted(clean.items())}
        print(f"  {key:<28} normal={normal} {src} (offset {offset:+.2f}, {len(daily)} วัน)")

    # 2) เซ็นเซอร์ กทม. — ประวัติผ่าน tele_canal (datum เดียวกับ warn/crit)
    canals, canal_hist = {}, {}
    try:
        raw = get("https://api-v3.thaiwater.net/api/v1/thaiwater30/public/canal_waterlevel")["data"]
        sn = json.load(open(sorted(glob.glob(os.path.join(BASE, "data", "snapshots", "snapshot-*.json")))[-1]))
        near = {c["name"]: c for c in sn.get("canals", [])}
        for s in raw:
            st = s.get("station") or {}
            nm = ((st.get("canal_name") or {}).get("th") or "").strip()
            if nm not in near:
                continue
            try:
                val_now = float(s.get("canal_value"))
            except (TypeError, ValueError):
                continue
            try:
                daily, offset = graph_daily(st.get("id"), "tele_canal", start, end,
                                            parse_dt(s.get("canal_datetime")), val_now)
            except Exception as e:
                print(f"WARN canal {nm}: {e}")
                if near[nm].get("warn") is not None:   # fallback เกณฑ์เตือนภัย
                    canals[nm] = {"normal": round(float(near[nm]["warn"]), 2), "source": "bma_warn"}
                time.sleep(1.2)
                continue
            time.sleep(1.2)
            pre = {d: v for d, v in daily.items() if datetime.date.fromisoformat(d) < cut}
            try:
                warn = float(near[nm]["warn"])
            except (TypeError, ValueError):
                warn = None
            normal, src = sane_normal(pre, oldest_median(daily), fallback=warn)
            canals[nm] = {"normal": normal, "source": src or "bma_warn"}
            clean = {d: v for d, v in daily.items() if abs(v - val_now) <= 2.8}
            canal_hist[nm] = {"name": nm, "normal": normal, "daily": sorted(clean.items())}
            print(f"  {nm:<28} normal={normal} {src} ({len(daily)} วัน)")
    except Exception as e:
        print("WARN canal:", e)

    norm_path = os.path.join(BASE, "data", "normal_levels.json")
    json.dump({"built_at": datetime.datetime.now().isoformat(timespec="seconds"),
               "definition": f"median ของค่าเฉลี่ยรายวัน ย้อนหลัง {DAYS_BACK} วัน ตัด {DAYS_TRIM} วันล่าสุดออก",
               "stations": out, "canals": canals}, open(norm_path, "w"), ensure_ascii=False, indent=1)
    hist_path = os.path.join(BASE, "data", "station_history.json")
    json.dump({"built_at": datetime.datetime.now().isoformat(timespec="seconds"),
               "stations": history, "canals": canal_hist}, open(hist_path, "w"), ensure_ascii=False)
    print("OK", norm_path, f"({len(out)} stations, {len(canals)} canals)")
    print("OK", hist_path, f"({len(history)} + {len(canal_hist)} series)")
    missing = set(WANT) - set(out)
    if missing:
        print("  WARN ไม่มีระดับปกติ:", missing)

if __name__ == "__main__":
    main()
