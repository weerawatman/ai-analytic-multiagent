# Phase I — Proactive Insight Pipeline: ทำงานเองไม่ต้องรอถาม

<!-- สร้างจาก _TEMPLATE-phase.md ก่อนเขียนโค้ด (Handoff Protocol §4.4 ข้อ 2) -->

> **สถานะ:** เสร็จฝั่งโค้ด + automated tests — verified offline + manual smoke (lifespan, uvicorn, Streamlit); live scheduling ค้าง (ดูท้ายไฟล์)
> **ผู้ดำเนินการ:** AI session (2026-07-18) ตามคำสั่ง owner "ดำเนินการต่อใน phase ถัดไปได้เลย, ทำทีละ phase" หลัง Phase G (`df3a5f4`) + Phase H (`fde9a2f`) verified
> **อ้างอิง:** [phase-g-to-k-grand-roadmap.md](phase-g-to-k-grand-roadmap.md) §8 — งานนี้อยู่ใต้ **§4 Delegation Guardrails ทุกข้อ**

---

## Scope

### ทำใน phase นี้ (In)
- [x] `backend/app/services/insight_store.py` — SQLite ใน `analytics.db` (WAL, ต่อจาก Phase H): ตาราง `insights`, `insight_feedback` ตาม schema roadmap §8
- [x] `backend/app/services/insight_pipeline.py` — job kind `insight_pipeline`, 5 ขั้นตอน: `refresh_snapshots → run_detectors → score_candidates → narrate_top → publish`; รวม `validate_narrative_numbers(narrative_th, evidence)` (INV-4) + fallback template แบบ deterministic เมื่อ LLM fail/hallucinate
- [x] `backend/app/services/scheduler_service.py` — `AsyncIOScheduler` ใน FastAPI lifespan, catch-up-on-startup (เช็คงาน `insight_pipeline` ล่าสุดจาก `job_store`, delay 120 วิหลัง start), nightly cron `insight_cron_hour`, defer เมื่อมี job `chat`/`onboarding`/`deep_onboarding` active (INV-6: ผ่าน `job_runner` เท่านั้น ไม่ใช้ threading/subprocess)
- [x] Config ใหม่: `insight_pipeline_enabled` (default False — ต้อง owner เปิดเอง), `insight_cron_hour=2`, `insight_narrate_top_k=8`, `insight_catchup_after_hours=24`, `insight_pipeline_max_seconds=1800`
- [x] `job_runner.py`: `start_insight_pipeline_job()` + `_run_insight_pipeline_job` (ตาม pattern `_run_snapshot_refresh_job`)
- [x] Route `api/routes/insights.py`: `GET /insights/`, `GET /insights/{id}`, `GET /insights/status`, `POST /insights/{id}/feedback`, `POST /insights/refresh`
- [x] `frontend/pages/insights.py` — Streamlit multipage แรกของโปรเจกต์ (auto-detect จาก `frontend/pages/`), การ์ด GA-style, ปุ่ม feedback 3 ปุ่ม, `st.cache_data(ttl=30)` (ไม่เพิ่ม fragment poll ใหม่ — INV-12)
- [x] เพิ่ม `apscheduler` ใน `backend/requirements.txt` (pure-Python, ไม่อยู่ใน FORBIDDEN_DEPS ของ INV-1)
- [x] Tests: `test_insight_store.py`, `test_insight_pipeline.py`, `test_scheduler_service.py` — ทำให้ INV-4/INV-6 เปลี่ยนจาก skip เป็น pass
- [x] Gate `gates/I-done.md` + `phase-summaries/phase-i.md`

### ไม่ทำใน phase นี้ (Out)
- Phase J/K: `insight_ranker.py` (ML), `embedding_service.py`, `sql_pattern_store.py`, `lesson_miner.py`, `digest_service.py`, curriculum
- Auto-สร้าง golden-question candidate จาก feedback `label="wrong"` — เป็นงาน Phase J (learning loop); Phase I แค่บันทึก feedback ให้ครบ
- Lazy narrate-on-first-view สำหรับ candidate นอก top-K — เก็บเป็น `status="scored"` ไว้เฉยๆ (ไม่ narrate, ไม่แสดงใน UI) รอ Phase J/K ต่อยอด
- Insight ranker / ML scoring — Phase I ใช้ heuristic score เท่านั้น (`score == rank_score` วันนี้)
- Live scheduler run บน production schedule จริงหลายวัน (เกณฑ์สำเร็จข้อ "≥5 insights/week" ต้องรอ owner run จริง)

---

## Locked decisions + Canonical names ที่ phase นี้แตะ

| รายการ | ที่มา |
|---|---|
| `insight_store.py`, `insight_pipeline.py`, `scheduler_service.py` | roadmap §4.2 |
| ตาราง `insights`, `insight_feedback` ใน `analytics.db` (ไม่แตะ `app.db` — INV-7) | roadmap §4.2 / §8 |
| `validate_narrative_numbers(narrative_th, evidence)` ใน `insight_pipeline.py` | roadmap §4.2, INV-4 |
| Scheduler: APScheduler `AsyncIOScheduler`, catch-up-on-startup หลัก, nightly โบนัส, defer เมื่อ chat/onboarding active | roadmap §3 |
| Config: `insight_pipeline_enabled`, `insight_cron_hour`, `insight_narrate_top_k`, `insight_catchup_after_hours` | roadmap §4.2 |
| Route `insights.py` | roadmap §4.2 |
| Job kind `insight_pipeline` ผ่าน `job_runner` เท่านั้น (INV-6) | roadmap §4.2 |
| Insight feed: `st.cache_data(ttl=30)`, ห้าม fragment poll ใหม่ | INV-12 |
| Grading/scoring ไม่ใช้ LLM เป็นกรรมการ — LLM แค่ narrate จาก evidence (INV-4 หลักการใหญ่ #1) | roadmap §2 ข้อ 1 |

---

## Definition of Done (กรอกจริงก่อนปิด phase — ห้ามติ๊กล่วงหน้า)

- [x] โค้ดครบตาม Scope In และไม่มีงานนอก scope
- [x] pytest เต็มชุดเขียว (รวม `test_roadmap_conformance.py`) — แนบผลรันจริงท้ายไฟล์
- [x] เกณฑ์สำเร็จของ phase (roadmap §8) ผ่านครบฝั่ง automated; live scheduling ค้าง (ต้อง owner รันจริงหลายวัน)
- [x] สร้าง gate artifact ใน `gates/I-done.md`
- [x] Deviation Log ว่าง **หรือ** ทุกแถวมี owner approve

---

## Deviation Log

| วันที่ | เรื่องที่เบี่ยง | เหตุผล | Owner approved? |
|---|---|---|---|
| | *(ว่าง)* | | |

---

## Verification

```powershell
# รันจาก repo root เสมอ (conftest ต้องการ)
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_roadmap_conformance.py -v
```

Manual (เมื่อพร้อม):
```powershell
# เปิดใช้งาน: ตั้ง INSIGHT_PIPELINE_ENABLED=true ใน .env แล้ว restart backend
# POST /api/v1/insights/refresh  → ดู GET /api/v1/insights/status + /api/v1/insights/
# เปิด Streamlit → แท็บ "insights" (multipage) → ดูการ์ด + กด feedback
```

---

## ผลเทสต์ / หลักฐานแนบท้าย

```
332 passed, 1 skipped in ~56s
```

- Conformance: INV-2/3/4/6/7/9/11 pass (INV-4, INV-6 เปลี่ยนจาก skip → pass รอบนี้); INV-8 skip (Phase J)
- Manual smoke (นอกเหนือ pytest): `lifespan()` เต็มรูปแบบผ่านไม่มี error; uvicorn จริง → `/health`, `/api/v1/insights/status`, `/api/v1/analytics/status` (ทั้งหมด 200), `POST /api/v1/insights/refresh` (202 → job done); Streamlit จริง → หน้าเดิม + `/insights` ใหม่ (ทั้งคู่ 200, multipage auto-nav ทำงาน)
- Gates: `I-done.md`, `phase-summaries/phase-i.md`
- **ไม่ commit / ไม่ push** ตามคำสั่ง owner ("ทำทีละ phase เมื่อจบ phase ก็พิจารณาก่อนต่อ phase ถัดไป")
