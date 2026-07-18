# Phase H Done

> **วันที่:** 2026-07-18
> **commit hash:** `fde9a2f` (docs summary `4a5cffb`; base Phase G `df3a5f4`)
> **phase doc:** [phase-h-analytics-engine.md](../phase-h-analytics-engine.md)
> **precondition:** [G3-baseline-recorded.md](G3-baseline-recorded.md) (INV-11) — มีอยู่ก่อนสร้าง `backend/app/analytics/`

## เกณฑ์สำเร็จ Phase H (roadmap §7)

| เกณฑ์ | สถานะ | หลักฐาน |
|---|---|---|
| Task 0: cp314 wheels verified + pinned | ✅ | Python 3.14.2; `scipy==1.18.0` cp314-win_amd64 installed; `pandas==2.3.3`, `numpy==2.5.1` pinned in `backend/requirements.txt`; statsmodels optional (cp314 wheel มี แต่ไม่บังคับ) |
| Detector suite green offline | ✅ | `test_detectors.py`, `test_forecasting.py`, `test_contribution.py` — รวมใน pytest เต็มชุด |
| Detectors จับ event อดีต ≥ 3 กรณี | ✅ synthetic | `test_historical_events_recall_three_cases`: (1) sales crash month (2) level shift (3) upward trend — offline; **live เทียบ owner-known months บน mirror ยังค้าง** |
| Backfill 36 เดือน < 10 นาที / incremental < 2 นาที | ⏳ pending live | โค้ด + job `snapshot_refresh` พร้อม (`POST /api/v1/analytics/refresh`); ยังไม่ได้รัน timed backfill บน mirror ใน session นี้ (SQL source อาจ offline) |

## pytest

```
302 passed, 3 skipped in ~53s
```

Conformance (`test_roadmap_conformance.py`): INV-2/3/7/9/11 **pass** ณ ship Phase H; INV-4/6/8 **skip** ณ ship (pass หลัง Phase I/J บน master)

## สิ่งที่ส่งมอบ (โค้ด)

- `backend/app/analytics/{detectors,forecasting,contribution}.py` — pure (INV-2)
- `snapshot_store.py` → `analytics.db` WAL; `snapshot_refresh_service.py` ใช้ `render_metric_sql` + `run_sql`
- Job kind `snapshot_refresh` ใน `job_runner.py`
- Route `api/routes/analytics.py`
- DS prompt `{analytics_context}` จาก detector summary
- Deps: numpy/pandas/scipy pinned

## Manual / human gates ที่ยังค้าง

1. Live backfill timing บน Postgres mirror (หรือ Fabric) — บันทึก elapsed ใน run note
2. Owner validation: detectors จับ ≥ 3 เดือนที่คนรู้อยู่แล้วจากข้อมูลจริง (ไม่ใช่แค่ synthetic)
3. Optional: `pip install statsmodels==0.14.6` เพื่อ STL/ETS
