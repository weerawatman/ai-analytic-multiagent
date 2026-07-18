# Phase K Done

> **วันที่:** 2026-07-18
> **commit hash:** N/A (working tree — owner will commit; base Phase J `08f3af2` / `fc5adfa`)
> **phase doc:** [phase-k-world-class.md](../phase-k-world-class.md)
> **precondition:** Phase I + J โค้ดพร้อม; live traffic ยัง cold start

## เกณฑ์สำเร็จ Phase K (roadmap §10)

| เกณฑ์ | สถานะ | หลักฐาน |
|---|---|---|
| Digest ออกอัตโนมัติต่อเนื่อง ≥ 4 สัปดาห์ | ⏳ pending live | `digest_service` + weekly scheduler + `scripts/generate_digest.py` + UI พร้อม; ยังไม่มี 4 สัปดาห์จริง — ไม่ invent |
| ทุก role มี curriculum pass-rate เป็นตัวเลขที่โตขึ้น | ⏳ pending live / ✅ offline | Offline: seed 4 roles + `pass_rate_pct` + study session mock อัปเดตตัวเลข (`test_curriculum_study.py`); live: ต้องเปิด `STUDY_ENABLED` + traffic |
| Owner ยืนยัน "ฉลาดขึ้นจริง" ด้วย eval trend chart | ⏳ pending owner / ✅ offline | `eval_service.eval_trend` + `GET /api/v1/eval/trend` + chart ใน `frontend/pages/digest.py`; ต้องมีหลายรอบ eval จริง + owner ยืนยัน |

## pytest

```
390 passed in ~88s
```

(ก่อน Phase K ตาม phase-j summary: **379 passed**)

Conformance (`test_roadmap_conformance.py`): INV-1..INV-9, INV-11 **pass**; `digest_service.py` ถูกสร้างแล้ว → INV-9 ครอบคลุม

## สิ่งที่ส่งมอบ (โค้ด)

- `digest_service.py` — published+useful insights + QoQ/YoY (calendar provisional) → `briefings/digests/{yyyy-ww}.json`
- `frontend/pages/digest.py` — digest + eval trend + curriculum pass-rate (cache_data, ไม่มี fragment poll)
- `curriculum_store.py` + seed DA/DS/DE/BA + `study_service.py` + `job_runner.start_study_job` (kind `study` ตาม §4.2)
- Scheduler: nightly study + Sunday digest (in-process; ไม่เพิ่ม job kind นอก freeze)
- `knowledge_store.aggregate_approved_knowledge` — global + theme override + lessons
- `eval_service.list_eval_runs` / `eval_trend` + API
- Config / `.env.example` / README / `scripts/generate_digest.py`
- Optional Phase E sandbox **ไม่ทำ** — บันทึก deferred ใน phase doc

## Manual / human gates ที่ยังค้าง

1. Live digest ≥ 4 สัปดาห์ (`DIGEST_ENABLED=true`)
2. Live curriculum pass-rate โตขึ้น (`STUDY_ENABLED=true` + CEO approve study results)
3. Owner ยืนยัน eval trend ว่า "ฉลาดขึ้นจริง"
4. O-3 period basis (fiscal vs calendar) — digest ติดป้าย provisional
5. Owner commit + push (agent ไม่ commit ตามคำสั่ง)
