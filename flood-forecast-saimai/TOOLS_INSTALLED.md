# รายการเครื่องมือ / การติดตั้งสำหรับโปรเจค flood-forecast-saimai

วันที่สร้าง: 2026-09-27
นโยบายของโปรเจคนี้: **ไม่ติดตั้งอะไรลงระบบส่วนกลางเลย** ใช้เฉพาะของที่มีอยู่แล้วใน macOS และแพ็กเกจใดๆ จะถูก confine ไว้ในโฟลเดอร์นี้เท่านั้น

## สิ่งที่ใช้ (ไม่ได้ติดตั้งเพิ่ม — มีอยู่ในระบบแล้ว)

| เครื่องมือ | ชนิด | ต้องถอนทิ้ง? |
|---|---|---|
| `curl` | macOS built-in | ไม่ต้อง |
| `python3` (stdlib เท่านั้น: urllib, json, datetime) | macOS built-in | ไม่ต้อง |
| Playwright browser (ผ่าน MCP ของ opencode) | เปิด browser ชั่วคราวเพื่ออ่านข่าว | ไม่ต้อง (ปิด tab เมื่อจบ) |

## สิ่งที่ติดตั้งเพิ่ม (จดไว้ถอนทิ้ง)

| รายการ | ตำแหน่ง | วิธีถอน |
|---|---|---|
| cron job อัปเดตข้อมูลรายชั่วโมง (นาที 23) | user crontab (บรรทัดที่มีคำ `flood-forecast-saimai`) | รัน `bash uninstall.sh` |
| LaunchAgent เว็บเซิร์เวอร์ dashboard พอร์ต 8765 (เปิดอัตโนมัติหลังรีสตาร์ท) | `~/Library/LaunchAgents/com.saimai-flood.dashboard.plist` + log ที่ `/tmp/saimai-dashboard.log` | รัน `bash uninstall.sh` |

เข้าถึง dashboard จากโทรศัพท์ (ผ่าน WiFi/VPN เดียวกับเครือข่ายบ้าน): `http://192.168.1.37:8765/dashboard.html`

ส่วนอื่นทั้งหมด (scripts, snapshots, dashboard.html) อยู่ในโฟลเดอร์โปรเจคนี้เท่านั้น — ไม่มี pip/npm/brew/venv ใดๆ

## วิธีถอนทิ้งทั้งหมด

```bash
bash flood-forecast-saimai/uninstall.sh
# หรือ
rm -rf flood-forecast-saimai
```

เพราะทุกอย่างอยู่ในโฟลเดอร์เดียว การลบโฟลเดอร์ = สะอาดหมด ไม่มี side effect กับระบบ

## API ภายนอกที่เรียกใช้ (read-only, ไม่มี account/key)

- Open-Meteo Forecast + Elevation API — https://open-meteo.com (ฟรี ไม่ต้องสมัคร)
- Nominatim (OpenStreetMap geocoding)
- api-v3.thaiwater.net (กรมชลประทาน/HII)
- Google News / เว็บข่าวไทย (อ่านผ่าน browser)
- **ตอนเปิด dashboard.html**: โหลดแผนที่ Leaflet + OpenStreetMap tiles + unpkg CDN ฝั่ง browser เท่านั้น (ไม่มีการติดตั้งใดๆ ถ้าออฟไลน์ส่วนอื่นของ dashboard ยังใช้ได้ แต่แผนที่จะไม่มีพื้นหลัง)
