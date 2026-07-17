# Phase G Done

> **วันที่:** 2026-07-18
> **base commit:** `d9c650e` + Phase G working tree (not committed — owner will commit)
> **phase doc:** [phase-g-foundation.md](../phase-g-foundation.md)

## เกณฑ์สำเร็จ Phase G (roadmap §6)

| เกณฑ์ | สถานะ | หลักฐาน |
|---|---|---|
| Heartbeat มองเห็นภายใน 30 วิ | ✅ automated | `heartbeat_at` + ticker 10s + API `health` + UI 3 สถานะ; tests in `test_job_heartbeat.py` |
| Registry ≥ 12, approved ≥ 8 | ✅ seeded | 15 metrics, **14 approved**, 1 draft (`metric.net_profit` — O-1 รอ BA); อัปเดต 2026-07-18 หลัง owner ตอบ O-1/O-2/O-3; `scripts/seed_metric_registry.py` |
| Baseline eval ถูกบันทึก | ✅ harness | [G3-baseline-recorded.md](G3-baseline-recorded.md) + `g3-harness-20260718.json` |
| answer_ratings เริ่มสะสม | ✅ code ready | table + API + UI; accumulation starts when users rate (manual) |

## pytest

```
274 passed, 7 skipped
```

## Manual / human gates ที่ยังค้าง

1. ~~Owner ตอบ O-1 / O-2 / O-3 แล้ว approve draft metrics~~ **ตอบแล้ว 2026-07-18:**
   - O-2 → `metric.discount_rate` approved **provisional** (`Price_Adjustment / Revenue` — รอ BA ยืนยันนิยามจริง)
   - O-3 → resolved: `Period_Year` = `Fiscal_Year`+`Period` (PERIO=GJAHR||PERDE) ≡ `SourceMonth` YYYYMM → `metric.qoq_revenue` / `metric.yoy_revenue` approved
   - O-1 → **ยังค้าง**: BA ยังไม่ให้สูตร Net Profit — `metric.net_profit` คง draft
2. BA ยืนยันสูตร Net Profit (O-1) + นิยาม discount rate ตัวจริง (แทน provisional O-2)
3. Live eval ผ่าน Ollama + SQL source (เมื่อ Fabric/Postgres พร้อม) → `G3-baseline-recorded-v2.md`
4. UI smoke: เปิด chat job ดู heartbeat / กด 👍👎
5. Owner commit + push (agent ไม่ commit ตามคำสั่ง)
