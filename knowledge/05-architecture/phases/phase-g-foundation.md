# Phase G — Foundation: มองเห็น, มีมาตรฐาน, มีไม้บรรทัด

<!-- สร้างจาก _TEMPLATE-phase.md ก่อนเขียนโค้ด (Handoff Protocol §4.4 ข้อ 2) -->

> **สถานะ:** เสร็จฝั่งโค้ด + automated tests — verified offline; live/manual gates ค้าง (ดูท้ายไฟล์)
> **ผู้ดำเนินการ:** AI session (2026-07-18) ตามคำสั่ง owner "อ่าน AGENTS.md แล้วทำ Phase G ตาม roadmap"
> **อ้างอิง:** [phase-g-to-k-grand-roadmap.md](phase-g-to-k-grand-roadmap.md) §6 — งานนี้อยู่ใต้ **§4 Delegation Guardrails ทุกข้อ**

---

## Scope

### ทำใน phase นี้ (In)
- [x] G1 Heartbeat UX — `heartbeat_at` + `touch_job` + runner ticker ~10s + jobs API `health` + frontend 3 สถานะ + `progress_reporter.note_substep` ใน DA retry
- [x] G1b Feedback capture — `answer_ratings` ใน app.db + `api/routes/ratings.py` + ปุ่ม 👍/👎 ใน Streamlit
- [x] G2 Metric Registry — `metric_registry.py` + seed 14 metrics + `render_metric_sql` + DA context (config flag) + insight_starter อ่าน registry + `api/routes/metrics.py` + seed script
- [x] G3 Golden-question eval v1 — `eval_service.py` + seed 20 คำถาม + `scripts/run_golden_eval.py` + baseline → `gates/G3-baseline-recorded.md`
- [x] Tests: `test_job_heartbeat.py`, `test_ratings_api.py`, `test_metric_registry.py`, `test_eval_service.py`
- [x] อัปเดต `.env.example`, README, local_paths (eval/ + metric_registry.json)

### ไม่ทำใน phase นี้ (Out)
- Phase H: `backend/app/analytics/`, snapshot store, detectors, pandas/scipy
- Phase I: insight pipeline, scheduler, insights UI page
- Phase J/K: embeddings, ranker, digest, curriculum
- Owner ตอบ O-1/O-2/O-3 แบบ live — metric ที่เกี่ยวข้อง seed เป็น **draft**
- Live E2E ผ่าน Ollama จริงสำหรับ baseline accuracy — บันทึก harness baseline แล้ว

---

## Locked decisions + Canonical names ที่ phase นี้แตะ

| รายการ | ที่มา |
|---|---|
| `progress_reporter.py` / `note_substep(thread_id, text)` | roadmap §4.2 |
| `touch_job(job_id)` / `heartbeat_at` | roadmap §6 G1 |
| `answer_ratings` ใน `app.db` | roadmap §4.2 |
| `metric_registry.py` / `render_metric_sql` / `metric_registry.json` | roadmap §4.2 / §6 G2 |
| `eval_service.py` / golden questions / eval/results | roadmap §4.2 / §6 G3 |
| Routes: `ratings.py`, `metrics.py`, `eval.py` | roadmap §4.2 |
| Config: `metric_registry_in_prompt` | roadmap §11 week-2 |

---

## Definition of Done

- [x] โค้ดครบตาม Scope In และไม่มีงานนอก scope
- [x] pytest เต็มชุดเขียว — **274 passed, 7 skipped** (รวม `test_roadmap_conformance.py`)
- [x] เกณฑ์สำเร็จของ phase (roadmap §6) ผ่านครบฝั่ง automated + harness baseline
- [x] สร้าง gate artifact: `gates/G3-baseline-recorded.md`, `gates/G-done.md`
- [x] Deviation Log ว่าง

---

## Deviation Log

| วันที่ | เรื่องที่เบี่ยง | เหตุผล | Owner approved? |
|---|---|---|---|
| | *(ว่าง)* | | |

---

## Open items (อัปเดตตามคำตอบ owner 2026-07-18)

| # | คำถาม | สถานะ | รายละเอียด |
|---|---|---|---|
| O-1 | สูตร Net Profit ใน CE1SATG | **ยังเปิด** — รอสูตรจาก BA | `metric.net_profit` คง **draft** (ห้าม invent สูตร). Owner ยืนยันซ้ำว่าสูตรธุรกิจเดิมเป็น source of truth: Vc=KFG0006, Fc ไม่รวม VVA18, COGS-Actual(business)=Vc+Fc (คนละตัวกับคอลัมน์ COGS_Actual=VVA01), Con. Margin=KFG0002-KFG0006, Gross Profit=KFG0002-VVA01, GP Inc. Defect=KFG0002-VVA01-VVC01, Revenue +Inter=KFG0002=VVR06+ERLOS+VVR01 |
| O-2 | นิยาม discount rate | **approved (provisional)** | Owner สั่งใช้ชั่วคราว: `Price_Adjustment / Revenue`. ตรวจแล้วคอลัมน์ `Price_Adjustment` (VVR02) มีจริงใน `CE1SATG_All_Cleaned` (มี `Price_Adjustment_RM`=VVR04 ด้วยแต่ไม่ใช้). เพิ่ม `metric.price_adjustment` + promote `metric.discount_rate` (v2) — ต้อง revisit เมื่อ BA ยืนยันนิยามจริง |
| O-3 | ฐานเวลา QoQ/YoY | **resolved** | ตรวจแล้ว `Period_Year` (PERIO) = `Fiscal_Year` (GJAHR) ต่อด้วย `Period` (PERDE) เช่น `2025005`='2025'+'005' และตรงกับ `SourceMonth`='202505' (หลักฐาน: `usp_Load_CE1SATG_Month.sql` CAST order + sample rows ใน discovery profile). `SourceMonth` (YYYYMM) จึงเทียบเท่า Fiscal_Year+Period ที่ granularity เดือน → `metric.qoq_revenue` / `metric.yoy_revenue` promote เป็น **approved** โดยใช้ `SourceMonth` เป็น time_column |

---

## Verification

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_roadmap_conformance.py -v
.\scripts\seed-metric-registry.ps1
.\.venv\Scripts\python.exe scripts\run_golden_eval.py --harness-baseline
```

---

## ผลเทสต์ / หลักฐานแนบท้าย

```
274 passed, 7 skipped in ~63s
```

- Registry seed: 14 total, 10 approved → `data/local/knowledge/metric_registry.json`
- อัปเดต 2026-07-18 (owner ตอบ O-1/O-2/O-3): **15 total, 14 approved, 1 draft** (`metric.net_profit` รอสูตรจาก BA) — เพิ่ม `metric.price_adjustment`, promote `metric.discount_rate` (provisional), `metric.qoq_revenue`, `metric.yoy_revenue`
- Baseline run_id: `g3-harness-20260718` → accuracy_pct=0.0 (harness; Fabric paused / PG timeout)
- Gates: `G3-baseline-recorded.md`, `G-done.md`
- **ไม่ commit / ไม่ push** ตามคำสั่ง owner
