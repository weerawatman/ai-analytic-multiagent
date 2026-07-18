# Phase H — Analytics Engine (สรุปท้าย phase)

**วันที่:** 2026-07-18  
**สถานะ:** โค้ด + automated tests เสร็จ; live backfill / owner-known event validation ยังค้าง  
**เอกสารหลัก:** [phase-h-analytics-engine.md](../knowledge/05-architecture/phases/phase-h-analytics-engine.md)  
**เกต:** [H-done.md](../knowledge/05-architecture/phases/gates/H-done.md) (ต้องมี [G3-baseline-recorded.md](../knowledge/05-architecture/phases/gates/G3-baseline-recorded.md) ก่อน — INV-11)

## สิ่งที่ทำแล้ว

- **Task 0** — verify cp314 wheels บน Python 3.14.2; pin `numpy==2.5.1`, `pandas==2.3.3`, `scipy==1.18.0` ใน `backend/requirements.txt` (statsmodels optional / import-guarded)
- **Pure analytics** — `detectors.py` (robust z / IQR / CUSUM / Theil-Sen+Mann-Kendall + optional STL), `forecasting.py` (seasonal naive + optional ETS + residual flags), `contribution.py` (GA-style drivers, mix-vs-rate, Pareto/HHI, churn/new)
- **Snapshot store** — `analytics.db` (WAL) ตาราง `metric_snapshots` + `snapshot_runs`; ไม่แตะ chat DB (INV-7)
- **Refresh service** — SQL จาก `render_metric_sql` เท่านั้น → `run_sql` + provenance; backfill 36 / incremental 3; Product_Number top-500 + `__other__`
- **Job + API** — kind `snapshot_refresh`; `GET/POST /api/v1/analytics/*`
- **DS integration** — `{analytics_context}` จาก detector summary บน snapshots
- **Tests** — detectors / contribution / forecasting / snapshot_store + roadmap conformance

## งานคงเหลือ

- Live timed backfill บน mirror (เกณฑ์ < 10 นาที / incremental < 2 นาที)
- Owner ยืนยัน detectors จับ event จริง ≥ 3 เดือนที่รู้แล้ว
- Optional install statsmodels สำหรับ STL/ETS
- ไม่ invent Phase I (insight pipeline / scheduler / Insights UI)

## เกตที่ค้าง

- Live backfill timing evidence
- Live owner-known event validation (synthetic ผ่านแล้วใน `test_historical_events_recall_three_cases`)
- Owner commit + push

## commits ที่เกี่ยวข้อง

- N/A จนกว่า owner จะ commit/push (ตามคำสั่ง — agent ไม่ commit)

## หมายเหตุ

- Baseline ก่อนเริ่ม H: `G3-baseline-recorded.md` (harness accuracy 0.0)
- pytest หลัง Phase H: **302 passed, 3 skipped** (ก่อนเก็บ Phase H ~281 collected / Phase G รายงาน 274 passed, 7 skipped)
