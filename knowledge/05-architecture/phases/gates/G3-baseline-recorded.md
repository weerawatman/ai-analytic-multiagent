# G3 Baseline Recorded

> **วันที่:** 2026-07-17
> **run_id:** `73ed48233039`
> **harness_baseline:** True
> **source note:** references resolve via Metric Registry + active SQL source when available; harness baseline uses empty answers (accuracy may be 0)

## Metrics

| Metric | Value |
|---|---|
| golden questions | 20 |
| accuracy_pct | 0.0 |
| sql_success_rate | 0.0 |
| median_latency_s | 0.0 |
| registry metrics (approved) | 10 / 14 |

## Result file

`C:\Projects\ai-analytic-multiagent\data\local\eval\results\73ed48233039.json`

## Notes

- This gate satisfies INV-11 (baseline before Phase H / `backend/app/analytics/`).
- Re-run with live chat pipeline (without `--harness-baseline`) when Ollama is available to refresh numbers — add `G3-baseline-recorded-v2.md` if replacing.
