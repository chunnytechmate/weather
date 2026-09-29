# Data sources และเครื่องมือสำหรับขยายงานติดตามน้ำ

เอกสารนี้รวมแหล่งข้อมูลและเครื่องมือที่ใช้ขยายโปรเจกต์จากซอยสายไหมไปเป็นการติดตามเขื่อนทั้งประเทศและเขื่อนต่างประเทศที่เกี่ยวข้อง พร้อมพยากรณ์ระดับน้ำที่แม่นขึ้น ผมตรวจ URL และยิงทดสอบ API จริงวันที่ Sep 29, 2026 ตัวที่ผ่านการทดสอบระบุว่า verify แล้ว ตัวที่ได้มาจากการค้นหาเท่านั้นระบุว่ายังไม่ verify

## เขื่อนในประเทศ: ข้อมูลมีอยู่แล้วใน API เดิม

### thaiwater analyst/dam (verify แล้ว ใช้อยู่ในโปรเจกต์)

endpoint เดียวครอบคลุมเขื่อนทั้งประเทศ ไม่ต้องหาแหล่งใหม่:

```
GET https://api-v3.thaiwater.net/api/v1/thaiwater30/analyst/dam
```

| กลุ่ม | จำนวน | รายละเอียด |
|---|---|---|
| `dam_hourly` | 17 | เขื่อน EGAT เกือบทั้งหมด อัปเดตรายชั่วโมง แต่บางแถวค้างข้อมูลปี 2020-2022 ต้องกรองวันที่ก่อนใช้ |
| `dam_daily` | ~50 แถว | เขื่อนใหญ่ 35 แห่งของ RID + 15 แห่งของ EGAT (เขื่อนเดียวอาจมี 2 record จาก 2 หน่วยงาน) แถว RID สดกว่า (วันนี้ vs เมื่อวาน) และแถว EGAT บางตัว % ความจุเป็น 0 ให้เลือกแถว RID ก่อน |
| `dam_medium` | ~800 | อ่างเก็บน้ำขนาดกลาง RID ทั้งประเทศ มีแถวเน่าวันที่ 1970-01-01 ปนอยู่ |
| `dam_small_tele` | 60 | อ่างเล็กแบบโทรมาตร |

สคริปต์ `fetch_snapshot.py` ของโปรเจกต์เก็บกลุ่ม dam_daily แบบ dedupe แล้วใน field `dams_all` ทุกชั่วโมงตั้งแต่ Sep 29, 2026 ต่อจากนี้เป็นการรอเวลาสะสมเท่านั้น

hostname เก่าที่เจอใน blog และ community repo ตายหมดแล้ว: `dgonline.thaiwater.net` (DNS ไม่ resolve) และ `api.thaiwater.net` (404) ตัวที่ใช้ได้จริงคือ `api-v3` เท่านั้น

### RID hyd-app-db: ประวัติระดับน้ำรายชั่วโมงย้อนหลัง (verify แล้ว)

ของที่ thaiwater ไม่ได้ให้ตรงๆ คือ historical รายชั่วโมงแบบ query ย้อนหลัง RID มี webservice แบบไม่ต้อง auth (ไม่มีเอกสารทางการ ชุมชนใช้กันเอง):

```
POST https://hyd-app-db.rid.go.th/webservice/HDService.svc/getStationGroup
     {"hydro": {"basinid": "10", "hydroid": "5"}}
POST .../HDService.svc/getStationGroupFromID   {"hydro": {"stationGroupID": <id>}}
POST .../HDService.svc/GetHourlyStageReport    {"hydro": {"StationGroupID": <id>, "TimeCurrent": "DD/MM/YYYY_BE"}}
```

วันที่ใช้พุทธศักราช เช่น "29/09/2569" ข้อควรระวัง: ไม่มีเอกสาร, certificate อาจต้อง bypass ใน client, response ใช้รูปแบบ `/Date(epoch_ms)/` เหมาะที่สุดสำหรับ backfill training data ของโมเดล ML ก่อนที่ snapshot ของเราจะสะสมยาวพอ

### แหล่งไทยอื่นๆ

| แหล่ง | สถานะ | ใช้ทำอะไร |
|---|---|---|
| `tiservice.hii.or.th/opendata/data_catalog/water_level/` | verify แล้ว | metadata สถานีทุกลุ่มน้ำ (CSV) + ข้อมูลย้อนหลังแบบ zip มีคู่ขนานสำหรับฝนและอุณหภูมิ |
| `data.tmd.go.th` (TMD Open Data) | verify แล้ว | NWP พยากรณ์ฝนของไทยเอง: 3 ชม./จุดถึง 10 วัน @18 กม., รายชั่วโมง 72 ชม. @6 กม., รายชั่วโมง 48 ชม. @2 กม. (ละเอียดกว่า Open-Meteo) สมัครขอ Bearer token ฟรี |
| `water.egat.co.th` | verify แล้ว | แผนการปล่อยน้ำเขื่อนใหญ่ กฟผ. และพยากรณ์น้ำเข้าอ่างรายเดือน ใช้เมื่อต้องการรู้ release ล่วงหน้า (ข้อมูล release ที่เกิดแล้วไหลเข้า thaiwater แล้ว) |
| `skdam.egat.co.th` | verify แล้ว | ข้อมูลเขื่อนสิริกิติ์เฉพาะ + แผนปล่อยน้ำ |
| `standard.thaiwater.net` | verify แล้ว | portal API ทางการใหม่ของ สสน. ต้องขอใช้เป็นทางการ |

## เขื่อนต่างประเทศที่เกี่ยวข้อง

ข้อสรุปเชิงภูมิศาสตร์ก่อน: **ลุ่มเจ้าพระยาอยู่ในไทยทั้งสาย ไม่มีเขื่อนต่างประเทศที่มีผลต่อน้ำกรุงเทพฯ** ฝนต้นน้ำก็ตกในไทยทั้งหมด เขื่อนต่างชาติที่มีผลกับประเทศไทยคือกลุ่มแม่น้ำโขง (เขื่อนจีนชุด Yunnan เช่น Xiaowan, Nuozhadu และเขื่อนลาว) ซึ่งกระทบอีสาน (ลุ่มมูล/ชี) และพื้นที่ริมโขง (เชียงรายถึงหนองคาย) ไม่ใช่ซอยสายไหม ถ้าเป้าหมายคือซอย ข้อมูลโขงเป็นบริบทภูมิภาคเท่านั้น ไม่เข้าโมเดล

| แหล่ง | สถานะ | ให้อะไร |
|---|---|---|
| `ffw.mrcmekong.org` (MRC) | verify แล้ว | พยากรณ์น้ำโขง 5 วัน อัปเดตรายวัน 22 สถานีจากเชียงแสนถึงเวียดนาม (ช่วงฤดูน้ำหลาก) + bulletin รายสัปดาห์ + สถานะ Alarm/Flooded |
| `mekongmonitor.stimson.org` (Mekong Dam Monitor) | verify แล้ว | virtual gauge จากดาวเทียม (Sentinel-1/2 + altimetry) ของเขื่อนจีน cascade ความแม่นราว ±1 เมตร อัปเดตรายสัปดาห์ ครอบคลุม ~13 เขื่อน ไม่มี API ทางการ ใช้อ่านบน dashboard |
| `www.lmcwater.org.cn` | verify แล้ว | แพลตฟอร์มของจีน แบ่งปันระดับน้ำรายวันสถานี Yunjinghong และ Man'an ตลอดปี (เว็บเดิม lmnc-center.org ตายแล้ว) |
| `dahiti.dgfi.tum.de` | verify แล้ว | altimetry time series ระดับอ่างเก็บน้ำทั่วโลก มี API v2 (สมัครฟรี + token) ครอบคลุมเขื่อนจีน คือทางเข้าแบบ machine-readable ที่ดีที่สุดสำหรับเขื่อนที่ประเทศเจ้าของไม่เปิดข้อมูล |
| `hydroweb.next.theia-land.fr` | verify แล้ว | ผลิตภัณฑ์ CNES ระดับน้ำจากดาวเทียมรวม SWOT เข้าถึงด้วย STAC API ฟรี |

สำหรับเขื่อนในไทยเอง ข้อมูล in-situ จาก thaiwater สดและแม่นกว่าดาวเทียม ดาวเทียมมีค่ากับเขื่อนต่างประเทศเป็นหลัก

## พยากรณ์สากลไว้เทียบ (baseline)

| เครื่องมือ | เข้าถึง | ให้อะไร |
|---|---|---|
| Copernicus GloFAS | ฟรี สมัคร account + `pip install cdsapi` แล้วดึงจาก EWDS (`ewds.climate.copernicus.eu/datasets/cems-glofas-forecast`) | river discharge พยากรณ์ global กริด ~5 กม. lead time 30 วัน ดึงที่จุดนครสวรรค์มาเทียบกับโมเดลเราได้ |
| Google Flood Hub | ดูฟรีที่ g.co/floodhub, API ฟรีแต่ต้องขอ waitlist (`developers.google.com/flood-forecasting`) | พยากรณ์น้ำท่วม 7 วัน + flash flood 24 ชม. ครอบคลุมไทยแล้ว (รอบขยาย พ.ค. 2023) |
| Open-Meteo (ใช้อยู่) | ฟรี | จุดที่ยังไม่ได้ใช้เต็มที่: `&models=ecmwf_ifs025,gfs,icon` เพื่อทำ ensemble ฝนเหนือเอง และ Historical Forecast API (`historical-forecast-api.open-meteo.com`) ที่เก็บพยากรณ์ย้อนหลังตั้งแต่ปี 2021 จำเป็นมากสำหรับ train ML ด้วยพยากรณ์จริงที่เคยออก ไม่ใช่ข้อมูลย้อนหลังสวยๆ |

## โมเดล hydrology เมื่อจะเอาจริง

ทางเดินที่ผมแนะนำเรียงจากถูกไปแพง:

1. **LightGBM/XGBoost ต่อสถานี** (เริ่มง่าย โปร่งใส) input คือระดับ 18 ชม. + ฝน NWP หลาย model + release เขื่อน + tide output คือระดับพรุ่งนี้ถึง 7 วัน ข้อมูลพร้อมหมดแล้วใน repo นี้
2. **neuralhydrology** (`github.com/neuralhydrology/neuralhydrology`, LSTM rainfall-runoff) มาตรฐานของงานวิจัย แนวทางเดียวกับที่ Google ใช้ทำ Flood Hub และเอาชนะ GloFAS ได้ในหลาย metric (Nearing et al. 2024, Nature: Global prediction of extreme floods in ungauged watersheds) ต้องมีข้อมูลสะสมอย่างน้อย 1 ฤดูน้ำ
3. **HEC-HMS** (ฝน → inflow เขื่อน) และ **HEC-RAS** (discharge นครสวรรค์ → ระดับน้ำถึงกรุงเทพฯ) โมเดลกายภาพของ US Army Corps ฟรี ทำงานหนักกว่า ML แต่อธิบายเชิงกลไกได้
4. **EPA SWMM + pyswmm** สำหรับโมเดลระบบคลองในเมืองโดยเฉพาะ เอาไว้เจาะระบบระบาย กทม. ละเอียดระดับซอย

## ลำดับงานแนะนำสำหรับคนต่อยอด

1. รอ snapshot สะสม 30 วันขึ้นไป (เริ่ม Sep 27, 2026) แล้ว fit K, rain_coef ของ lag-route โมเดลเดิมจากข้อมูลจริง แทนค่าตั้งมือ
2. Backfill ประวัติรายชั่วโมงจาก RID HDService.svc กับ `waterlevel_graph` ของ thaiwater เพื่อให้ train ได้เร็วขึ้นไม่ต้องรอ
3. ดึงฝน multi-model จาก Open-Meteo + Historical Forecast API เป็นชุด input พยากรณ์จริง
4. เทียบกับ GloFAS และ Google Flood Hub เป็น baseline ก่อนเขียนโมเดลใหม่
5. เขียน LightGBM ต่อสถานี เทียบกับ persistence forecast (พรุ่งนี้เท่ากับวันนี้) ซึ่งเป็น baseline ที่แสนจะ beat ยากในงานระดับน้ำ
6. ขยับเป็น neuralhydrology เมื่อมีข้อมูล 1-2 ฤดู

## Sources ทั้งหมด

**ไทย:** api-v3.thaiwater.net/api/v1/thaiwater30/analyst/dam · standard.thaiwater.net · water.egat.co.th (+ /API/serviceList.php) · skdam.egat.co.th/index.php/water-data · hyd-app-db.rid.go.th/webservice/HDService.svc · telerid.rid.go.th · wmsc.rid.go.th · tiservice.hii.or.th/opendata/data_catalog/water_level/ · data.hii.or.th · data.tmd.go.th · tiwrm.hii.or.th/DATA/REPORT/php/egat_dam.php

**โขง/ต่างประเทศ:** ffw.mrcmekong.org (+ /bulletin.php) · portal.mrcmekong.org (+ /dsmp/dsmp-description) · monitoring.mrcmekong.org · mekongmonitor.stimson.org · stimson.org/2022/mekong-dam-monitor-tutorial-and-faq · www.lmcwater.org.cn

**พยากรณ์/ดาวเทียม:** global-flood.emergency.copernicus.eu · ewds.climate.copernicus.eu/datasets/cems-glofas-forecast · github.com/ecmwf/cdsapi · g.co/floodhub · developers.google.com/flood-forecasting · open-meteo.com · dahiti.dgfi.tum.de/en/api/doc/v2/ · hydroweb.next.theia-land.fr

**โมเดล:** hec.usace.army.mil/software/hec-hms · hec.usace.army.mil/software/hec-ras · epa.gov/water-research/storm-water-management-model-swmm · github.com/pyswmm/pyswmm · github.com/neuralhydrology/neuralhydrology

**อ้างอิง community:** github.com/korarit/flood-analysis-model (โค้ดอ้างอิง RID webservice) · github.com/clemensv/real-time-sources (สรุป thaiwater API)
