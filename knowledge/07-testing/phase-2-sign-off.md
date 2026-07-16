# Phase 2 Sign-off Checklist

**Project:** AI Fabric Insight Explorer  
**Phase:** 2 — Autonomous Data Team + CEO Loop + Knowledge  
**Date:** _____________  
**Owner:** Data Engineer (CEO role for HITL)

---

## Automated checks

Run:

```powershell
.\scripts\validate-phase2.ps1
```

Or API: `GET /api/v1/validation/phase2`

---

## Manual verification

| # | Check | Done |
|---|-------|------|
| 1 | Select theme → discovery runs automatically (columns + samples cached) | ☐ |
| 2 | CEO Briefing shows 4-role briefs after discovery | ☐ |
| 3 | CEO approve/reject/comment saved to `data/local/feedback/{theme_id}.json` | ☐ |
| 4 | Ask "ยอดขาย 2026 รายเดือน" → SQL uses real columns (not guessed SAP names) | ☐ |
| 5 | SQL invalid column → auto-retry with schema context | ☐ |
| 6 | Add glossary entry in Knowledge panel → agents read it in next question | ☐ |
| 7 | BA summary appears in collaborative Explore response | ☐ |
| 8 | Approve glossary entry → status `approved` | ☐ |
| 9 | Fabric remains read-only (no write DDL/DML) | ☐ |

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Data Engineer / CEO | | | |

**Notes:**

---

## Phase 2 complete when

- All automated P2-* checks pass (or documented exceptions)
- Manual items 1–9 verified
- At least one theme: discovery → briefing → CEO question → quality output
