# Triage policy

## Categories

| Code | Meaning | Typical signals |
|------|---------|-----------------|
| `env` | Tooling / ports / missing `.env` | health fail, port in use, no `.venv` |
| `llm` | Ollama unreachable, OOM, model missing | all agents ⚠️ `ขั้นตอนนี้ทำงานไม่สำเร็จ`, ConnectionError, HTTP 500 from Ollama |
| `sql` | Fabric/Postgres/guard | ProgrammingError, offline skip unexpected, provenance wrong |
| `code` | Application logic bug | assertion in product path, wrong agent order |
| `test` | Flaky or missing coverage | test isolation leak; gap → `qa-test-engineer` |
| `human-gate` | Needs owner | Trusted, KPI O-1/O-2, production claim |

## SCN-LLM-001 pattern (known)

Symptom: Explore job heartbeat green but DE/DS/DA/BA all failed sanitized notes.

Likely `llm` (not Fabric): OOM on large model, wrong `OLLAMA_BASE_URL`, model not pulled.

Checks:

1. `ollama list`
2. `.env` → `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
3. Optional: `ollama run <model> "ping"` or generate API smoke
4. `data/local/logs/backend.log` for exception type (keep detail out of committed reports)

## Repair rules

1. One category cluster per round.
2. Prefer config fix for `env`/`llm` before code changes.
3. Never delete or skip INV tests.
4. Suspected bad test → open defect as `test`; do not silently change expected business numbers.
5. After 3 rounds → defect handoff + readiness = not ready.

## Honesty

| Label | Allowed when |
|-------|----------------|
| test-passed | L1 green |
| code-complete | Merged/fixed code + tests green (still may lack live) |
| production-verified | Live env + owner evidence only |
| human-gate-pending | Any open Trusted/KPI/owner item |
