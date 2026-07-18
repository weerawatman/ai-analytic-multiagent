# Readiness assessment — 2026-07-18 / full-system

> **QA recommendation only — not owner sign-off**
> **Run (DEF-001 regression):** `20260718-203027-487673`
> **Prior failing run:** `20260718-191418-3b7689`
> **Linked report:** [`../run-reports/2026-07-18-model-downsize-20260718-203027-487673.md`](../run-reports/2026-07-18-model-downsize-20260718-203027-487673.md)
> **Prior report:** [`../run-reports/2026-07-18-full-system-20260718-191418-3b7689.md`](../run-reports/2026-07-18-full-system-20260718-191418-3b7689.md)

## Recommendation

| Label | Status |
|-------|--------|
| Safe for owner **manual Explore** smoke? | **with caveats** — SCN-ENV-002 เขียวบน `qwen2.5-coder:3b`; คุณภาพต่ำกว่าเป้า ~14B; Fabric pause → ใช้ Postgres/offline พร้อม label |
| Offline test-passed? | **yes** (390 pytest + 11 conformance) |
| Live pipeline verified? | **not-run / partial** — SCN-CHAT-001 หยุดเพราะ wall-time cap บน CPU |
| Production-verified? | **no** |

## Caveats

- DEF-001 ปิดด้วยโมเดลเล็กลง (3b) — ไม่ใช่การยืนยันว่า 7b/14b พร้อมบนเครื่องนี้
- Fabric capacity ไม่ active → live Fabric SQL ไม่พร้อม; fallback ต้องมี label (ไม่ silent)
- L2 / SCN-CHAT-001 ไม่จบภายใน ~10–12 นาทีบน CPU Ollama
- Golden live `answer_fn` ยัง deferred (SCN-GQ-002)

## Open defects

| DEF-ID | Severity | Blocks manual test? |
|--------|----------|---------------------|
| [DEF-001](../defect-handoffs/DEF-001-ollama-oom-configured-model.md) | high → **Fixed** | **no** สำหรับ generate smoke; คุณภาพ Explore ยัง caveat |

## Human gates still open

- [ ] Trusted promotion
- [ ] KPI / metric formula (O-1 / O-2 / …)
- [ ] Fabric capacity / live SQL confirmation
- [ ] Owner production sign-off
- [ ] Optional later: free RAM / upgrade back toward 7b–14b for Phase 1 quality bar

## Suggested owner next step

1. Manual Explore สั้น ๆ ได้ (คาดคุณภาพ 3b + อาจช้าบน CPU)
2. ถ้าต้องการ L2 เต็ม: เพิ่มเวลา/GPU หรือรันนอก peak RAM
3. Commit/push รายงานนี้เมื่อพร้อม (ต้องสั่งเอง)

---

1. Recommendation for manual Explore: **yes, with caveats** (3b quality; Fabric pause; L2 chat not fully verified)
2. **production-verified: no**
3. **Commit/push: not performed**
