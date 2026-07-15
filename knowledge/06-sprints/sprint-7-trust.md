# Build Sprint 7 — Trusted Promotion HITL

**Stage:** 06 Build  
**Date:** 2026-07-15  
**Stories:** TRUST-1  
**Status:** Complete — pending commit sign-off

---

## Delivered

| Story | Implementation |
|-------|----------------|
| TRUST-1 | `promotion_service.py` — preview metric from validated backlog |
| TRUST-1 | `GET /api/v1/semantic/promote/{id}/preview` |
| TRUST-1 | `POST /api/v1/semantic/promote/{id}/approve` → `trusted.json` + status `promoted` |
| TRUST-1 | `promotion_panel.py` — HITL preview, edit fields, Approve/Reject |
| TRUST-1 | Trusted mode — Analyst constrained to approved definitions only |

## HITL Flow

1. Backlog item status `validated` or `discussing`
2. กด **Promote to Trusted** → preview Markdown
3. แก้ metric/playbook ได้ (optional)
4. Approve → เขียน `data/local/semantic/trusted.json` + backlog `promoted`
5. Trusted mode ใช้ definitions ที่ promote แล้ว

## Tests

- `test_promotion_service.py`
- `test_semantic_promote_api.py`

## Next Sprint

Build Sprint 8 — VALID-1 (Phase 1 end-to-end validation)
