#!/usr/bin/env python3
"""
โมเดล forecast ระดับน้ำท่วมขัง ท้ายซอยสายไหม 44 กรุงเทพฯ
วิธีทำงาน: scenario-based water balance
  depth(t+1) = depth(t) + ฝนใหม่ที่คลองรับไม่ไหว - อัตราการระบาย(t)
  อัตราการระบายถูก modulate ด้วย 3 ปัจจัย: ฝนคงเหลือ, ระดับเจ้าพระยา (มวลน้ำเหนือ 27-29 ก.ย.), น้ำหนุน spring tide (สูงสุด 27-28 ก.ย.)
ข้อมูลป้อน: data/openmeteo_forecast.json + ข้อมูลสนามจากผู้ใช้ (27 ก.ย. ~17:45)
"""
import json
from datetime import datetime, timedelta

# ---- ข้อมูลสนาม (จากผู้ใช้, 27 ก.ย. 2569 ~17:45) ----
DEPTH_NOW = 20.0      # ซม. (ผู้ใช้ตอบ 10-30 ซม.)
DEPTH_LO, DEPTH_HI = 10.0, 30.0
TREND = "stable"      # เทียบเมื่อวาย คงที่
FLOW = "still"        # น้ำนิ่ง

# ---- ฝน forecast (Open-Meteo, จุด 13.918N 100.651E) ----
f = json.load(open("data/openmeteo_forecast.json"))
daily = f["daily"]
rain = dict(zip(daily["time"], daily["precipitation_sum"]))

# ปริมาณฝนคงเหลือของวันนี้ (27) + พรุ่งนี้ (28) ประมาณจาก hourly
hourly = f["hourly"]
rain_rest_27 = sum(p or 0 for t, p in zip(hourly["time"], hourly["precipitation"])
                   if t.startswith("2026-09-27") and t >= "2026-09-27T18:00")
rain_28 = rain.get("2026-09-28", 0)

# ---- สัมประสิทธิ์แปลงฝนเป็นน้ำขังเพิ่ม (คลองล้นเต็มระบบ) ----
# ประสบการณ์ กทม.: ฝน 100 มม./วัน ตอนคลองล้น → น้ำขังเพิ่ม ~30-50 ซม. → ratio ~0.3-0.5
RUNOFF_RATIO = 0.35

# ---- อัตราการระบาย (ซม./วัน) ต่อวัน: (base, ลด, เพิ่ม) ----
# base = เครื่องสูบ+ประตูเปิดช่วงน้ำลงของกระแส
# 27-28 ก.ย.: ฝนยังเติม + น้ำหนุนสูงสุด + เจ้าพระยาขึ้น (มวลน้ำเหนือ) → ระบายได้น้อยมาก
# 29 ก.ย.: ฝนหมด แต่ยังมีน้ำหนุนรอบใหม่ + เจ้าพระยายังสูง → เริ่มไหล
# 30 ก.ย.-1 ต.ค.: น้ำหนุนลด เจ้าพระยาทรงและลด → ระบายเต็ม
# 2 ต.ค.: เต็มสูง
DRAIN_RATES = {  # วัน: (ต่ำ, ฐาน, สูง) ซม./วัน
    "2026-09-28": (0, 5, 10),
    "2026-09-29": (5, 10, 15),
    "2026-09-30": (10, 18, 25),
    "2026-10-01": (15, 25, 35),
    "2026-10-02": (20, 30, 40),
    "2026-10-03": (20, 30, 40),
}

def run(depth0, ratio, rates_idx):
    """คืน list ของ (วัน, ระดับตอน 18:00) — ฝนคืนนี้(27)ตกลงถึงเช้ามืดวันที่ 28"""
    out, d = [], depth0
    rain_in = {"2026-09-28": rain_rest_27 + rain_28}
    for i, (day, (lo, base, hi)) in enumerate(DRAIN_RATES.items()):
        rate = (lo, base, hi)[rates_idx]
        add = rain_in.get(day, 0) * ratio
        d = max(0.0, d + add - rate)
        out.append((day, round(d, 1)))
    return out

print(f"ฝนคงเหลือคืนนี้ (27 18:00→): {rain_rest_27:.1f} มม. | วันที่ 28: {rain_28:.1f} มม.")
print(f"ระดับน้ำเริ่มต้น: {DEPTH_NOW:.0f} ซม. (ช่วง {DEPTH_LO:.0f}-{DEPTH_HI:.0f})\n")

scenarios = {"ช้า (worst)": 0, "ฐาน (base)": 1, "เร็ว (best)": 2}
results = {}
for name, idx in scenarios.items():
    res = run(DEPTH_NOW, RUNOFF_RATIO, idx)
    results[name] = res
    print(f"== {name} ==")
    for day, d in res:
        print(f"  {day} 18:00 → {d:5.1f} ซม.")
    dry = next((day for day, d in res if d <= 5), None)
    walkable = next((day for day, d in res if d <= 10), None)
    print(f"  เหลือ <=10 ซม. (วอกได้): {walkable} | <=5 ซม. (แฉะ/ใกล้แห้ง): {dry}\n")

# จุดเริ่มเห็น "ลดชัดเจน" = วันแรกที่อัตราระบาย > ฝนเติม สะสมเป็นลบต่อเนื่อง
print("จุดเปลี่ยนแนวโน้ม: ค่ำ 28 → เช้า 29 ก.ย. (ฝนท้องถิ่นหมด คลองหลักเริ่มลด แต่ช่วงเช้ามืด/เย็นน้ำหนุนยังอัดระดับ)")
