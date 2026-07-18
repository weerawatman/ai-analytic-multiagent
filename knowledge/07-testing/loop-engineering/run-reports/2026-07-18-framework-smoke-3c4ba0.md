# Run report — 20260718-190834-3c4ba0

> **วันที่:** 2026-07-18
> **Scope:** framework-smoke (Loop Engineering QA bootstrap)
> **Level:** 1
> **Environment label:** mixed (local services up; Fabric live not claimed)
> **Raw evidence:** `data/local/qa/loop-engineering/runs/20260718-190834-3c4ba0/` (gitignored)

## Summary

| Metric | Value |
|--------|-------|
| L0 env smoke | pass (`start.ps1 -Status`; generate skipped via `-SkipOllamaGenerate`) |
| L1 pytest | pass (**390** passed) |
| L1 conformance | pass (**11** passed) |
| L2 live / golden | not run (Level 1) |
| Repair rounds used | 0 / 3 |

## Scenarios executed

| SCN-ID | Result | Notes |
|--------|--------|-------|
| SCN-ENV-001 | pass | start.ps1 -Status |
| SCN-ENV-002 | skip | generate skipped for this smoke |
| SCN-OFF-001 | pass | pytest exit 0 |
| SCN-INV-001 | pass | conformance exit 0 |
| SCN-CHAT-001 | skip | Level 1 only |
| SCN-LLM-001 | skip | Level 1 only — still relevant for manual Explore if agents fail |
| SCN-SRC-001 | skip | Level 1 only |
| SCN-GQ-001 | skip | Level 1 only |
| SCN-GATE-001 | skip | human-gate |

## Failures (sanitized)

None in this run.

## Honesty labels

- [x] code-complete (framework artifacts present)
- [x] test-passed (offline)
- [ ] production-verified — **only with live + owner evidence**
- [x] human-gate-pending (Trusted / KPI / live eval still open)

## Next actions

1. Before manual Explore: ensure Ollama model loads (SCN-ENV-002 generate, not tags-only) — prior UI incident SCN-LLM-001.
2. Owner may run Level 2 when ready: `.\scripts\run-readiness-check.ps1 -Level 2` (long).
3. Deferred: wire live golden `answer_fn` (SCN-GQ-002).

## Commit / push

**Not performed by Loop Engineering unless the user explicitly asks.**
