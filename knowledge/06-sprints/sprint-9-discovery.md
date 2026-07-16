# Sprint 9 — Discovery + Schema Context

**Goal:** Fix invalid column SQL by profiling theme tables before LLM runs.

## Deliverables

| ID | Item | Status |
|----|------|--------|
| S9-1 | `discovery_service.py` — columns, row count, samples, relationships | Done |
| S9-2 | `POST /api/v1/discovery/{theme_id}/run` | Done |
| S9-3 | Auto-trigger discovery on theme select (`theme_panel.py`) | Done |
| S9-4 | Schema Context Pack in agent prompts | Done |
| S9-5 | SQL auto-retry on `Invalid column name` (`data_analyst.py`) | Done |
| S9-6 | Tests: `test_discovery_service.py` | Done |

## Acceptance

- `data/local/knowledge/themes/{id}/discovery.json` created after theme pick
- Analyst prompt includes real column names from discovery cache
