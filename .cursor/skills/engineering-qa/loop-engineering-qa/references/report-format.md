# Report format

## Paths

| Kind | Path | Committed? |
|------|------|------------|
| Raw run | `data/local/qa/loop-engineering/runs/<run_id>/` | No (`data/local/` ignored) |
| Run report | `knowledge/07-testing/loop-engineering/run-reports/` | Yes (sanitized) |
| Defect | `knowledge/07-testing/loop-engineering/defect-handoffs/` | Yes (sanitized) |
| Readiness | `knowledge/07-testing/loop-engineering/readiness/` | Yes (recommendation only) |

## Naming

- Run report: `YYYY-MM-DD-<scope>-<run_id>.md`
- Readiness: `YYYY-MM-DD-<scope>-readiness.md`
- Defect: `DEF-<nnn>-<slug>.md`

Use templates under `knowledge/07-testing/loop-engineering/templates/`.

## Sanitization

Committed docs may include:

- Pass/fail counts, SCN IDs, exception **type** names
- Thai user-facing summaries
- Commands run (no secrets)

Must **not** include:

- `.env` values, tokens, connection strings
- Full ODBC / SQLSTATE dumps
- Large production row samples
- Anthropic / API keys

## Required closing lines

Every readiness assessment ends with:

1. Recommendation for manual Explore (yes/no/caveats)
2. Explicit **production-verified: no** unless owner evidence exists
3. **Commit/push: not performed** (or note if user requested)
