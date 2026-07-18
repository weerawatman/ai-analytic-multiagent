# Readiness assessment — 2026-07-18 / framework-smoke

> **QA recommendation only — not owner sign-off**
> **Run:** `20260718-190834-3c4ba0`
> **Linked report:** [`../run-reports/2026-07-18-framework-smoke-3c4ba0.md`](../run-reports/2026-07-18-framework-smoke-3c4ba0.md)

## Recommendation

| Label | Status |
|-------|--------|
| Safe for owner **manual Explore** smoke? | **with caveats** — offline suite green; confirm Ollama model inference before chat |
| Offline test-passed? | **yes** (390 pytest + 11 conformance) |
| Live pipeline verified? | **not-run** |
| Production-verified? | **no** |

## Caveats

- L0 generate smoke was skipped in this run (`-SkipOllamaGenerate`). If Explore shows all agents ⚠️, triage as SCN-LLM-001 (OOM / wrong model / URL).
- Fabric connected status was not asserted as production evidence.
- Golden live answer_fn still deferred (SCN-GQ-002).

## Open defects

| DEF-ID | Severity | Blocks manual test? |
|--------|----------|---------------------|
| _(none opened this run)_ | — | — |

## Human gates still open

- [ ] Trusted promotion
- [ ] KPI / metric formula (O-1 / O-2 / …)
- [ ] Fabric capacity / live SQL confirmation
- [ ] Owner production sign-off

## Suggested owner next step

1. Confirm Ollama model loads: `ollama list` + short `ollama run <model> ping` (or re-run readiness without `-SkipOllamaGenerate`).
2. Manual Explore with theme selected; if agents fail, invoke Loop Engineering skill for SCN-LLM-001 triage.
3. Commit/push this framework when ready (user-requested).
