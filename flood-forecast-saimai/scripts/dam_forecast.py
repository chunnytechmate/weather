"""คาดการ % ความจุเขื่อนล่วงหน้า 30 วัน แบบสถิติเรียบง่าย + ทดสอบย้อนหลัง

ไม่ใช่แผนระบายน้ำของ กฟผ./กรมชลฯ และไม่รู้ฝนล่วงหน้า เป็นการต่อเส้นจากข้อมูลที่มี:
  A) แนวโน้ม: อัตราเปลี่ยนเฉลี่ย 7 วันล่าสุด (จุด%/วัน) ค่อยๆ อ่อนลงครึ่งหนึ่งทุก HALF_LIFE วัน
     (น้ำไหลเข้าช่วงพีคไม่คงอยู่ตลอด และเขื่อนเต็มจะถูกเร่งระบาย)
  B) ปีที่แล้ว: ใช้การเปลี่ยนแปลงรายวันของช่วงวันเดียวกันปีที่แล้ว (จับฤดูกาลได้ เช่น ปลายฝนน้ำยังเข้า)
  ค่ากลาง = เฉลี่ย A,B · แถบ = ช่วงระหว่าง A,B กว้างขึ้นด้วยความคลาดเคลื่อนจากการทดสอบย้อนหลัง
  ขอบบน/ล่าง: ไม่เกินความจุสูงสุด (รสส.) และไม่ต่ำกว่า dead storage"""
import datetime

HORIZON = 30
HALF_LIFE = 10.0


def _d(s):
    return datetime.date.fromisoformat(s)


def paths(series, ly_series, t0, horizon=HORIZON):
    """series/ly_series: {date: pct} · ly_series วันที่เลื่อน +1 ปีแล้ว · คืน (A, B) เป็น list ยาว horizon"""
    base = series.get(t0)
    d7 = series.get((_d(t0) - datetime.timedelta(days=7)).isoformat())
    if base is None or d7 is None:
        return None
    r0 = (base - d7) / 7
    a, b, va, vb = [], [], base, base
    for t in range(1, horizon + 1):
        va += r0 * 0.5 ** (t / HALF_LIFE)
        day = (_d(t0) + datetime.timedelta(days=t)).isoformat()
        prev = (_d(t0) + datetime.timedelta(days=t - 1)).isoformat()
        if ly_series.get(day) is not None and ly_series.get(prev) is not None:
            vb += ly_series[day] - ly_series[prev]
        else:
            vb = va if vb is None else vb + (va - (a[-1] if a else base))
        a.append(va)
        b.append(vb)
    return a, b


def backtest(all_series, all_ly, origins, hs=(7, 14, 30)):
    """MAE (จุด%) ของวิธีนี้เทียบ persistence (= ค่าคงที่เท่าวันเริ่ม) ทุกเขื่อน ทุกวันเริ่มใน origins"""
    err = {h: [] for h in hs}
    per = {h: [] for h in hs}
    for name, s in all_series.items():
        for t0 in origins:
            p = paths(s, all_ly.get(name, {}), t0, max(hs))
            if not p:
                continue
            for h in hs:
                truth = s.get((_d(t0) + datetime.timedelta(days=h)).isoformat())
                if truth is None:
                    continue
                err[h].append(abs((p[0][h - 1] + p[1][h - 1]) / 2 - truth))
                per[h].append(abs(s[t0] - truth))
    mae = lambda v: round(sum(v) / len(v), 2) if v else None
    return {h: {"model": mae(err[h]), "persistence": mae(per[h]), "n": len(err[h])} for h in hs}


def forecast(series, ly_series, t0, lo_cap, hi_cap, err):
    """คืน [[date, center, lo, hi], ...] · err = {h: MAE} ใช้ขยายแถบ"""
    p = paths(series, ly_series, t0)
    if not p:
        return []
    out = []
    hs = sorted(err)
    for t in range(1, HORIZON + 1):
        a, b = p[0][t - 1], p[1][t - 1]
        h = next((x for x in hs if x >= t), hs[-1])
        e = (err[h] or 0) * t / h if t < h else (err[h] or 0)
        c = (a + b) / 2
        lo, hi = min(a, b) - e, max(a, b) + e
        clamp = lambda v: max(lo_cap, min(hi_cap, v))
        out.append([(_d(t0) + datetime.timedelta(days=t)).isoformat(),
                    round(clamp(c), 2), round(clamp(lo), 2), round(clamp(hi), 2)])
    return out
