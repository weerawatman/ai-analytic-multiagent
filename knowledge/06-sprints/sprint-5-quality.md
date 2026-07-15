# Build Sprint 5 — Quality Bar D & Agent Prompts

**Stage:** 06 Build  
**Date:** 2026-07-15  
**Stories:** EXPLORE-2, AGENT-1  
**Status:** Complete — pending commit sign-off

---

## Delivered

| Story | Implementation |
|-------|----------------|
| EXPLORE-2 | `quality_assembly.py`, `quality_node.py` — Bar D payload + Thai markdown |
| EXPLORE-2 | Explore pipeline: analyst → critique → quality_assembly → summarize |
| AGENT-1 | Updated DE/Analyst/Scientist prompts — Fabric T-SQL, Thai output, assumptions |
| AGENT-1 | Agents use `fabric_sql.py` instead of PostgreSQL when Fabric configured |

## API

| Method | Path |
|--------|------|
| POST | `/api/v1/chat/save-candidate` — save Quality Bar D payload to backlog |

## Chat Response

Includes `quality_payload` and `quality_gaps` in Explore mode.

## UI

Sidebar button **บันทึก Candidate ล่าสุด** when quality payload available.

## Tests

- `test_quality_assembly.py`

## Next Sprint

Build Sprint 6 — HANDOFF-1 (Thai Markdown export)
