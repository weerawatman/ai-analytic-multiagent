# Run report — {{run_id}}

> **วันที่:** {{date}}
> **Scope:** {{scope}}
> **Level:** {{level}}
> **Environment label:** {{env_label}}  <!-- offline | fabric | postgres | mixed -->
> **Raw evidence:** `data/local/qa/loop-engineering/runs/{{run_id}}/` (gitignored)

## Summary

| Metric | Value |
|--------|-------|
| L0 env smoke | {{l0_status}} |
| L1 pytest | {{l1_status}} ({{passed}}/{{total}}) |
| L1 conformance | {{inv_status}} |
| L2 live / golden | {{l2_status}} |
| Repair rounds used | {{rounds}} / 3 |

## Scenarios executed

| SCN-ID | Result | Notes |
|--------|--------|-------|
| {{scn_id}} | pass/fail/skip | {{note}} |

## Failures (sanitized)

- Category: `env` | `llm` | `sql` | `code` | `test` | `human-gate`
- Exception type only (no ODBC dumps / secrets)
- Link defect handoff if opened: `defect-handoffs/DEF-…`

## Honesty labels

- [ ] code-complete
- [ ] test-passed (offline)
- [ ] production-verified — **only with live + owner evidence**
- [ ] human-gate-pending

## Next actions

1. …
2. …

## Commit / push

**Not performed by Loop Engineering unless the user explicitly asks.**
