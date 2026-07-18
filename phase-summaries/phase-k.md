# Phase K — World-class Layer (สรุปท้าย phase)

**วันที่:** 2026-07-18
**สถานะ:** โค้ด + automated tests เสร็จ; live §10 success criteria ค้าง (digest ต่อเนื่อง / pass-rate / owner eval trend)
**เอกสารหลัก:** [phase-k-world-class.md](../knowledge/05-architecture/phases/phase-k-world-class.md)
**เกต:** [K-done.md](../knowledge/05-architecture/phases/gates/K-done.md)

## สิ่งที่ทำแล้ว

- **digest_service.py** — board digest รายสัปดาห์ (insights published+useful + metric QoQ/YoY provisional) → `data/local/briefings/digests/{yyyy-ww}.json`; optional Claude polish ผ่าน redaction
- **frontend/pages/digest.py** — หน้า digest + eval trend chart + curriculum pass-rate (st.cache_data)
- **curriculum_store.py** — seed DA/DS/DE/BA + pass-rate เป็นตัวเลข
- **study_service.py** + **job_runner.start_study_job** — kind `study` (canonical); ผลเข้า team memory `pending_ceo_approve`
- **knowledge aggregate** — global + per-theme override + sql lessons
- **eval trend** — list runs + API `/eval/trend`
- Scheduler: nightly study + Sunday digest; digest หลัง insight_pipeline เมื่อ flag เปิด
- **Tests:** ~11 เคสใหม่ — ชุดเต็ม **390 passed** (ก่อนหน้า 379)

## งานคงเหลือ

- Live: digest ≥ 4 สัปดาห์, curriculum pass-rate โตจริง, owner ยืนยัน eval trend
- O-3 ล็อก period basis แล้วเอาป้าย provisional ออก
- Optional Phase E sandbox (`execute_python`) — ยังไม่เริ่ม (deferred)

## เกตที่ค้าง

- Live §10 metrics (ดู K-done.md)
- Owner commit/push

## commits ที่เกี่ยวข้อง

- N/A จนกว่า owner จะสั่ง commit/push

## หมายเหตุ

- Roadmap G→K **ครบฝั่งโค้ด** แล้ว (G–K); ไม่ invent phase ถัดไป
- ไม่ commit/push ใน session นี้ตามคำสั่ง
