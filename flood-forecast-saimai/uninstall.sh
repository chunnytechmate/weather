#!/bin/bash
# ถอนทิ้งโปรเจค flood-forecast-saimai ทั้งหมด (cron + LaunchAgent + ไฟล์ทั้งหมด)
set -e
( crontab -l 2>/dev/null | grep -v "flood-forecast-saimai" ) | crontab - 2>/dev/null || true
echo "ลบ cron job แล้ว (ถ้ามี)"
launchctl bootout gui/$(id -u)/com.saimai-flood.dashboard 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.saimai-flood.dashboard.plist
rm -f /tmp/saimai-dashboard.log
echo "ลบ LaunchAgent เว็บเซิร์เวอร์แล้ว"
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "ลบ: $DIR"
rm -rf "$DIR"
echo "เสร็จสิ้น — ไม่มีสิ่งอื่นตกค้างในระบบ"
