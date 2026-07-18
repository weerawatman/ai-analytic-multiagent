# Phase I Done

> **วันที่:** 2026-07-18
> **commit hash:** `2525108` (base Phase H `fde9a2f`)
> **phase doc:** [phase-i-proactive-insights.md](../phase-i-proactive-insights.md)
> **precondition:** Phase H (`fde9a2f`) + Phase G1b (`answer_ratings`, already shipped)

## เกณฑ์สำเร็จ Phase I (roadmap §8)

| เกณฑ์ | สถานะ | หลักฐาน |
|---|---|---|
| Pipeline รันจบเอง unattended (nightly หรือ catch-up) | ✅ โค้ด/⏳ live | `scheduler_service.py`: catch-up-on-startup (120s delay, เช็คจาก `job_store` job kind `insight_pipeline` ล่าสุด), nightly cron `insight_cron_hour`, defer เมื่อ chat/onboarding active — unit-tested ครบ (`test_scheduler_service.py`); **ยังไม่ได้รันจริงต่อเนื่องหลายวันบน production schedule** (ต้อง owner เปิด `INSIGHT_PIPELINE_ENABLED=true` แล้วปล่อยรัน) |
| ≥ 5 insights/สัปดาห์; ≥ 30% "มีประโยชน์" ภายในเดือนแรก; "ข้อมูลผิด" < 10% | ⏳ pending live | โค้ดพร้อมวัด (`insight_store.feedback_stats()`, `GET /api/v1/insights/status`) แต่ต้องมี insight ที่เผยแพร่จริงสะสมเป็นสัปดาห์/เดือนก่อนจึงมีตัวเลขนี้ได้ — ยังไม่มีข้อมูลจริงในระบบ ณ วันที่เขียน gate นี้ |
| Detection latency ≤ 24 ชม. หลังข้อมูลลง mirror | ✅ ตามการออกแบบ | pipeline ทุกรอบเรียก `refresh_snapshots(mode="auto")` (incremental 3 เดือน) ก่อน `run_detectors` เสมอ — เมื่อ scheduler รันตามคาบที่กำหนด (catch-up ≤24ชม. + nightly) latency ตามดีไซน์เป็นไปตามเกณฑ์; ยังไม่มีหลักฐาน live เพราะยังไม่เปิดใช้งานจริง |
| ตัวเลขใน narrative ที่ไม่อยู่ใน evidence = 0 กรณี | ✅ | `validate_narrative_numbers` (INV-4) บังคับทุก narrative ผ่าน job `insight_pipeline`; retry 1 ครั้งแล้ว fallback แบบ deterministic ที่ไม่มีทางหลอน — ยืนยันด้วย `test_insight_pipeline.py` (accept/reject/fallback/end-to-end ทุกเคส) |

## pytest

```
332 passed, 1 skipped in ~56s
```

Conformance (`test_roadmap_conformance.py`): INV-2/3/4/6/7/9/11 **pass** ณ ship Phase I (INV-4, INV-6 เปลี่ยนจาก skip → pass รอบนี้); INV-8 **skip** ณ ship (pass หลัง Phase J บน master)

## สิ่งที่ส่งมอบ (โค้ด)

- `backend/app/services/insight_store.py` — ตาราง `insights`, `insight_feedback` ใน `analytics.db` (WAL, ไม่แตะ `app.db` — INV-7)
- `backend/app/services/insight_pipeline.py` — 5 ขั้นตอน `refresh_snapshots → run_detectors → score_candidates → narrate_top → publish`; `validate_narrative_numbers` (INV-4); fallback narrative แบบ deterministic
- `backend/app/services/scheduler_service.py` — `AsyncIOScheduler`, catch-up-on-startup, nightly cron, defer เมื่อ chat/onboarding active (INV-6)
- `backend/app/services/job_runner.py` — job kind `insight_pipeline` (`start_insight_pipeline_job`, `_run_insight_pipeline_job`, 5-step progress timeline)
- Config: `insight_pipeline_enabled` (default **False** — ต้อง owner เปิดเอง), `insight_cron_hour`, `insight_narrate_top_k`, `insight_catchup_after_hours`, `insight_pipeline_max_seconds`
- Route `backend/app/api/routes/insights.py`: `GET /insights/`, `GET /insights/{id}`, `GET /insights/status`, `POST /insights/{id}/feedback`, `POST /insights/refresh`
- `frontend/pages/insights.py` — Streamlit multipage แรกของโปรเจกต์ (auto-detect), `st.cache_data(ttl=30)`, ไม่เพิ่ม fragment poll ใหม่ (INV-12)
- Deps: `apscheduler==3.11.0` (pure Python, ยืนยันติดตั้งสำเร็จบน cp314)
- Tests: `test_insight_store.py` (7), `test_insight_pipeline.py` (12), `test_scheduler_service.py` (11)

## Manual smoke test ที่ทำแล้วรอบนี้ (นอกเหนือ pytest)

1. `lifespan()` เต็มรูปแบบ (init DB ทุกตัว + `scheduler_service.start()`/`shutdown()`) — ผ่าน ไม่มี error
2. รัน backend จริงด้วย uvicorn ชั่วครู่ → `GET /health` (200), `GET /api/v1/insights/status` (200), `GET /api/v1/analytics/status` (200), `POST /api/v1/insights/refresh` (202, job ทำงานจนจบ status=done)
3. รัน Streamlit จริงชั่วครู่ → หน้าเดิม `/` (200) และหน้าใหม่ `/insights` (multipage auto-nav, 200) — ไม่มี exception ใน log

## Manual / human gates ที่ยังค้าง

1. เปิด `INSIGHT_PIPELINE_ENABLED=true` แล้วปล่อยรันจริงต่อเนื่อง ≥ 1 สัปดาห์ — เก็บสถิติ insights/week + useful%/wrong% จริง
2. Owner สมัคร/ทดสอบกด feedback 3 ปุ่มในหน้า Streamlit จริงเพื่อยืนยัน UX
3. Live backfill ต้องเสร็จก่อน (Phase H gate ค้างอยู่) — ไม่งั้น `run_detectors` จะไม่มี snapshot ให้วิเคราะห์ (สังเกตจาก smoke test: `row_count:0` เพราะยังไม่เคย backfill จริงบน mirror)
