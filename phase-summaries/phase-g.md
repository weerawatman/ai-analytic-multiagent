# Phase G — Foundation (สรุปท้าย phase)

**วันที่:** 2026-07-18  
**สถานะ:** โค้ด + automated tests เสร็จ; live/manual gates ยังค้างบางส่วน  
**เอกสารหลัก:** [phase-g-foundation.md](../knowledge/05-architecture/phases/phase-g-foundation.md)  
**เกต:** [G-done.md](../knowledge/05-architecture/phases/gates/G-done.md), [G3-baseline-recorded.md](../knowledge/05-architecture/phases/gates/G3-baseline-recorded.md)

## สิ่งที่ทำแล้ว

- **G1 Heartbeat UX** — `heartbeat_at`, `touch_job`, runner ticker ~10s, jobs API `health`, frontend 3 สถานะ, `progress_reporter.note_substep`
- **G1b Ratings** — ตาราง `answer_ratings`, API `ratings`, ปุ่ม 👍/👎 ใน Streamlit
- **G2 Metric Registry** — `metric_registry.py`, seed (~15 metrics), `render_metric_sql`, DA context + insight_starter, API `metrics`, seed scripts; template ใต้ `data/templates/knowledge/`
- **G3 Eval harness** — `eval_service.py`, golden questions template, `scripts/run_golden_eval.py`, baseline harness `g3-harness-20260718`
- **Open items (บางส่วน):**
  - **O-2** — discount rate ใช้ชั่วคราว `Price_Adjustment / Revenue` (provisional / รอ BA)
  - **O-3** — verified: `Period_Year` ≡ `Fiscal_Year`+`Period` ≡ `SourceMonth` → QoQ/YoY approved
  - **O-1** — Net Profit ยัง draft (ห้าม invent สูตร)
- **Tests:** heartbeat / ratings / metric registry / eval + roadmap conformance (รายงานใน phase doc: 274 passed, 7 skipped)

## งานคงเหลือ

- O-1: รับสูตร Net Profit จาก BA แล้ว promote `metric.net_profit`
- O-2: BA ยืนยันนิยาม discount จริง (แทน provisional)
- Live eval ผ่าน Ollama + SQL เมื่อ Fabric/Postgres พร้อม → baseline v2
- UI smoke: เปิด chat ดู heartbeat / กด rating

## เกตที่ค้าง

- Manual UI smoke (heartbeat + 👍👎)
- Live golden eval (harness baseline accuracy = 0.0 เพราะ Fabric paused / PG timeout)
- BA sign-off O-1 (+ revisit O-2)

## commits ที่เกี่ยวข้อง

- `df3a5f4` — `feat(phase-g): heartbeat, ratings, metric registry, eval harness; resolve O-2/O-3`
- base ก่อนงานนี้: `d9c650e` (roadmap G→K docs)

## หมายเหตุ

- `data/local/knowledge/metric_registry.json` อยู่ใต้ `data/local/` (gitignore) — ใช้ template + seed script เป็น source of truth ใน git
