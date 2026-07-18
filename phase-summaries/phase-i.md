# Phase I — Proactive Insight Pipeline (สรุปท้าย phase)

**วันที่:** 2026-07-18
**สถานะ:** โค้ด + automated tests เสร็จ; live scheduling (`INSIGHT_PIPELINE_ENABLED=true` รันจริงหลายวัน) ยังค้าง
**เอกสารหลัก:** [phase-i-proactive-insights.md](../knowledge/05-architecture/phases/phase-i-proactive-insights.md)
**เกต:** [I-done.md](../knowledge/05-architecture/phases/gates/I-done.md)

## สิ่งที่ทำแล้ว

- **insight_store.py** — ตาราง `insights` + `insight_feedback` ใน `analytics.db` (WAL, INV-7)
- **insight_pipeline.py** — 5 ขั้นตอน `refresh_snapshots → run_detectors → score_candidates → narrate_top → publish`; `validate_narrative_numbers` บังคับทุก narrative (INV-4) — hallucinated number → retry 1 ครั้ง → fallback template ที่ไม่มีทางหลอน
- **scheduler_service.py** — `AsyncIOScheduler`, catch-up-on-startup (120s delay หลัง start, เช็ค job `insight_pipeline` ล่าสุดจาก job_store), nightly cron, defer เมื่อ chat/onboarding active (INV-6)
- **job_runner.py** — job kind `insight_pipeline` (5-step progress timeline เหมือน `snapshot_refresh`)
- Config ใหม่ 5 ตัว, default `insight_pipeline_enabled=False` (ต้อง owner เปิดเอง)
- Route `api/routes/insights.py` (list/get/status/feedback/refresh) + `frontend/pages/insights.py` (Streamlit multipage แรกของโปรเจกต์)
- Dep ใหม่: `apscheduler==3.11.0` (pure Python, ไม่ชนกับ INV-1)
- **Tests:** insight_store / insight_pipeline / scheduler_service (30 tests ใหม่) — INV-4, INV-6 เปลี่ยนจาก skip เป็น pass
- **Manual smoke:** lifespan เต็มรูปแบบ, uvicorn จริง (health/insights/analytics endpoints), Streamlit จริง (หน้าเดิม + `/insights` ใหม่) — ทั้งหมดผ่านไม่มี error

## งานคงเหลือ

- เปิด `INSIGHT_PIPELINE_ENABLED=true` แล้วปล่อยรันจริง ≥ 1 สัปดาห์ — เก็บสถิติ insights/week, useful%, wrong%
- Live backfill (Phase H gate ค้างอยู่) ต้องเสร็จก่อน — ตอนนี้ `analytics.db` ยัง row_count=0 จึงไม่มี snapshot ให้ detector วิเคราะห์จริง
- Owner ทดสอบกด feedback 3 ปุ่มในหน้า Streamlit จริง

## เกตที่ค้าง

- Live scheduling evidence (insights/week + useful/wrong %)
- Live backfill (สืบเนื่องจาก Phase H)
- Owner UI smoke (หน้า insights)

## commits ที่เกี่ยวข้อง

- ยังไม่ commit ในรอบนี้ (working tree) — base ก่อนงานนี้: `fde9a2f` (Phase H)

## หมายเหตุ

- Phase J/K (`insight_ranker`, `embedding_service`, `sql_pattern_store`, `lesson_miner`, `digest_service`) ยังไม่ทำ — INV-8 ยัง skip ตามคาด
- Lazy narrate-on-first-view สำหรับ candidate นอก top-K ยังไม่ทำ UI (เก็บเป็น `status="scored"` เฉยๆ ใน DB รอ Phase J/K)
- Auto-สร้าง golden-question จาก feedback `label="wrong"` ยังไม่ทำ (Phase J learning loop)
