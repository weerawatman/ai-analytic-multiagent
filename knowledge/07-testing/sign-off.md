# Phase 1 Sign-Off — AI Fabric Insight Explorer

**Date:** 2026-07-15  
**Owner:** Data Engineer  
**Status:** Draft — pending real Fabric theme cycle

---

## Automated Validation

Run from project root:

```powershell
.\scripts\validate-phase1.ps1
```

Or via API (backend running):

```
GET /api/v1/validation/phase1
```

Or in Streamlit sidebar: **Phase 1 Validation** panel.

---

## Manual Journey Checklist (Real Fabric Theme)

Complete on `WH_SAP_PRD` with Service Principal configured in `.env`:

| Step | Action | Done |
|------|--------|------|
| 1 | Start backend + frontend (`scripts/run-backend.ps1`, `run-frontend.ps1`) | [ ] |
| 2 | Verify Fabric health in sidebar | [ ] |
| 3 | Schema scan → pick 1 of 3 themes | [ ] |
| 4 | Explore mode: ask 1+ questions, get Quality Bar D output | [ ] |
| 5 | Save insight candidate to backlog | [ ] |
| 6 | Export Thai Markdown handoff report | [ ] |
| 7 | Record BA/DA feedback → status `validated` | [ ] |
| 8 | Promote to Trusted → HITL Approve | [ ] |
| 9 | Trusted mode: ask question using promoted metric | [ ] |
| 10 | Re-run `validate-phase1.ps1` → all checks pass | [ ] |

---

## PRD Definition of Done

- [ ] Fabric connected read-only with SP
- [ ] Schema scan proposes 3 themes; user picks 1
- [ ] ≥1 insight candidate passes Quality Bar D and enters backlog
- [ ] Export report generated in Thai
- [ ] BA/DA feedback recorded
- [ ] ≥1 item promoted to Trusted with playbook + example questions
- [ ] No PostgreSQL dependency in runtime path
- [ ] `data/local/` gitignored; templates committed

---

## Acceptance Criteria (AC-1 – AC-10)

See `knowledge/03-prd/acceptance-criteria/phase-1-core-loop.md`

| AC | Summary | Auto-check ID |
|----|---------|---------------|
| AC-1 | Fabric read-only + SQL guard | AC-1-guard, AC-1-fabric |
| AC-4 | Quality Bar D backlog | AC-4 |
| AC-5 | Thai export | AC-5, DoD-export-file |
| AC-6 | BA/DA feedback | AC-6 |
| AC-7 | Trusted HITL promotion | AC-7 |
| AC-8 | Trusted mode | AC-8 |
| AC-9 | Local JSON + SQLite | AC-9 |
| AC-10 | data/local gitignored | AC-10 |

---

## Owner Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Data Engineer (owner) | | | |

**Notes:**

---

## Evidence (fill after real run)

- **Theme chosen:**
- **Backlog item ID(s):**
- **Trusted metric_key:**
- **Export file path:**
