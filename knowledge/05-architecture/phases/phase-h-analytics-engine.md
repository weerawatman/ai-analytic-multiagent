# Phase H — Analytics Engine: สมองสถิติจริง

<!-- สร้างจาก _TEMPLATE-phase.md ก่อนเขียนโค้ด (Handoff Protocol §4.4 ข้อ 2) -->

> **สถานะ:** เสร็จฝั่งโค้ด + automated tests — verified offline; live backfill / owner-known months ค้าง (ดูท้ายไฟล์)
> **ผู้ดำเนินการ:** AI session (2026-07-18) ตามคำสั่ง owner "ดำเนินการ phase ถัดไป" หลัง Phase G (`df3a5f4` / `05fcb24`)
> **อ้างอิง:** [phase-g-to-k-grand-roadmap.md](phase-g-to-k-grand-roadmap.md) §7 — งานนี้อยู่ใต้ **§4 Delegation Guardrails ทุกข้อ**

---

## Scope

### ทำใน phase นี้ (In)
- [x] Task 0: verify cp314 Windows wheels ของ pandas/numpy/scipy (+statsmodels optional) → pin ใน `backend/requirements.txt`
- [x] `backend/app/analytics/` — pure functions: `detectors.py`, `forecasting.py`, `contribution.py` (+ Pareto/HHI/churn helpers)
- [x] `snapshot_store.py` → `data/local/analytics/analytics.db` (WAL) ตาราง `metric_snapshots`, `snapshot_runs`
- [x] `snapshot_refresh_service.py` — render SQL จาก registry → `run_sql` + provenance; backfill 36 เดือน / incremental 3 เดือน; Product_Number top-500 + `__other__`
- [x] Job kind `snapshot_refresh` ผ่าน `job_runner`
- [x] Route `api/routes/analytics.py` — สถานะ snapshot, อ่าน series, ปุ่ม refresh
- [x] DS agent prompt ได้ `{analytics_context}` จาก detector สรุปล่าสุดของ theme
- [x] Tests: `test_detectors.py`, `test_contribution.py`, `test_forecasting.py`, `test_snapshot_store.py` (+ conformance บังคับทันทีเมื่อ module เกิด)
- [x] อัปเดต `local_paths`, `.env.example`, README ตามที่จำเป็น
- [x] Gate `gates/H-done.md` + `phase-summaries/phase-h.md`

### ไม่ทำใน phase นี้ (Out)
- Phase I: `insight_store`, `insight_pipeline`, `scheduler_service`, Insights UI page, narration/validator
- Phase J/K: embeddings, ranker, digest, curriculum, sklearn
- Prophet / vector DB / Redis / Celery (INV-1)
- Cube 2 มิติ (locked: 1-D slices เท่านั้น)
- Live backfill timing proof บน mirror ถ้า SQL source offline — บันทึกเป็น pending gate

---

## Locked decisions + Canonical names ที่ phase นี้แตะ

| รายการ | ที่มา |
|---|---|
| Stats stack: pandas + numpy + scipy required; statsmodels optional import-guarded; ไม่ใช้ prophet | roadmap §3 |
| Snapshot grain: 1-D slices; Product_Number top-500 + `__other__` | roadmap §3 |
| `data/local/analytics/analytics.db` (WAL) — ไม่แตะ chat DB | roadmap §3 / INV-7 |
| `detectors.py`, `forecasting.py`, `contribution.py` | roadmap §4.2 |
| `snapshot_store.py`, `snapshot_refresh_service.py` | roadmap §4.2 |
| Route `analytics.py`; job kind `snapshot_refresh` | roadmap §4.2 |
| SQL ผ่าน `render_metric_sql` + `run_sql` เท่านั้น | INV-3, INV-9 |
| Analytics modules pure (ไม่ I/O / LLM) | INV-2 |
| G3 baseline ต้องมีก่อนสร้าง `analytics/` | INV-11 — มีแล้วที่ `gates/G3-baseline-recorded.md` |

---

## Definition of Done

- [x] โค้ดครบตาม Scope In และไม่มีงานนอก scope
- [x] pytest เต็มชุดเขียว — **302 passed, 3 skipped** (รวม `test_roadmap_conformance.py`)
- [x] เกณฑ์สำเร็จของ phase (roadmap §7) ผ่านครบฝั่ง automated + synthetic events; live timing ค้าง
- [x] สร้าง gate artifact: `gates/H-done.md`
- [x] Deviation Log ว่าง

---

## Deviation Log

| วันที่ | เรื่องที่เบี่ยง | เหตุผล | Owner approved? |
|---|---|---|---|
| | *(ว่าง)* | | |

---

## Verification

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_roadmap_conformance.py -v
```

Live (เมื่อ mirror พร้อม):
```powershell
# POST /api/v1/analytics/refresh  body: {"mode":"backfill"}
# ตรวจ GET /api/v1/analytics/status + snapshot_runs
```

---

## ผลเทสต์ / หลักฐานแนบท้าย

```
302 passed, 3 skipped in ~53s
```

- cp314: `scipy-1.18.0-cp314-cp314-win_amd64.whl` installed successfully
- Conformance: INV-2/3/7/9/11 pass; INV-4/6/8 skip (Phase I/J)
- Historical events ≥ 3: synthetic suite in `test_historical_events_recall_three_cases`
- **ไม่ commit / ไม่ push** ตามคำสั่ง owner
