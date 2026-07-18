# Scenario catalog (Loop Engineering)

Stable IDs for readiness runs. Automation levels: `script` | `agent` | `manual` | `human-gate`.

## env-smoke

### SCN-ENV-001 — Local services health

| Field | Value |
|-------|-------|
| Level | L0 |
| Automation | script |
| Preconditions | Repo checkout; preferably `.env` present |
| Steps | `.\scripts\start.ps1 -Status`; GET `/health`; Streamlit `/_stcore/health`; Ollama `/api/tags` |
| Expected | Backend/Frontend/Ollama status reported; no silent crash |
| Evidence | `summary.json` L0 section |

### SCN-ENV-002 — Ollama model inference smoke

| Field | Value |
|-------|-------|
| Level | L0 |
| Automation | script |
| Preconditions | Ollama reachable; `OLLAMA_MODEL` in `.env` or default |
| Steps | `ollama list`; optional short generate (`hi` / 1 short prompt) |
| Expected | Model listed; generate returns without OOM/connection error |
| Evidence | L0 `ollama_generate` status in summary |
| Notes | Tags-only health is **not** enough — agents need loadable weights |

## offline-unit

### SCN-OFF-001 — Full offline pytest

| Field | Value |
|-------|-------|
| Level | L1 |
| Automation | script |
| Steps | `.\.venv\Scripts\python.exe -m pytest backend/tests -q` from repo root |
| Expected | All tests pass (or documented skips only) |
| Evidence | pytest exit code + counts in `summary.json` |

## conformance

### SCN-INV-001 — Roadmap conformance invariants

| Field | Value |
|-------|-------|
| Level | L1 |
| Automation | script |
| Steps | `pytest backend/tests/test_roadmap_conformance.py -q` |
| Expected | INV-* enforced or legitimately skipped until module exists; never deleted |
| Evidence | conformance section in summary |
| Human-gate | No — but weakening tests is forbidden |

## agent-pipeline

### SCN-CHAT-001 — Explore question end-to-end

| Field | Value |
|-------|-------|
| Level | L2 |
| Automation | script (`run_quality_chat_test.py` / `run_quality_chat_direct.py`) or agent+UI |
| Preconditions | Backend up; Ollama model loadable; theme selected; Fabric and/or Postgres |
| Steps | Submit Explore question (e.g. sales from CE1SATG); wait job; inspect steps |
| Expected | DE→DS→DA→BA complete or graceful offline; provenance labeled; no raw SQL errors to CEO |
| Evidence | Job progress + sanitized answer |

## ollama-failure

### SCN-LLM-001 — All agents fail sanitized (regression of known incident)

| Field | Value |
|-------|-------|
| Level | L0 then L2 |
| Automation | agent + script |
| Preconditions | Reproduce or detect: heartbeat green, DE/DS/DA/BA all `ขั้นตอนนี้ทำงานไม่สำเร็จ` |
| Steps | Triage as `llm` per skill triage-policy; verify model load; fix config; re-run SCN-CHAT-001 |
| Expected | Root cause classified; either fixed or defect handoff with exception type |
| Evidence | Defect handoff + readiness caveat |
| Related | UI sanitizer hides details → always check `backend.log` |

## data-source

### SCN-SRC-001 — Fabric pause → labeled fallback

| Field | Value |
|-------|-------|
| Level | L2 |
| Automation | script / agent |
| Preconditions | Fabric paused or unreachable; Postgres mirror and/or disk cache available |
| Steps | Explore or theme scan; inspect provenance |
| Expected | No silent Fabric claim; label `postgres` or `offline`; Thai guidance when SQL skipped |
| Evidence | Provenance field / UI caption |

## golden

### SCN-GQ-001 — Golden harness baseline

| Field | Value |
|-------|-------|
| Level | L2 |
| Automation | script |
| Steps | `.\scripts\run-golden-eval.ps1` (harness / `--harness-baseline` as supported) |
| Expected | Questions load; result JSON written under `data/local/eval/results/` |
| Evidence | `accuracy_pct` / path in summary |
| Notes | **Live chat `answer_fn` not fully wired yet** — treat live accuracy as deferred |

### SCN-GQ-002 — Golden live pipeline (deferred)

| Field | Value |
|-------|-------|
| Level | L2 |
| Automation | script (future) |
| Status | **deferred** until `eval_service.run_eval` accepts live answer_fn from chat graph |
| Expected | Numeric/keyword grade against Metric Registry references |

## owner-gate

### SCN-GATE-001 — Trusted / KPI human approval

| Field | Value |
|-------|-------|
| Level | Human |
| Automation | human-gate |
| Steps | QA lists open Trusted/KPI items; does **not** approve |
| Expected | Readiness marks `human-gate-pending` |
| Approver | Owner only |

---

## Coverage checklist for framework DoD

- [x] SCN-ENV-001
- [x] SCN-ENV-002
- [x] SCN-OFF-001
- [x] SCN-INV-001
- [x] SCN-CHAT-001
- [x] SCN-LLM-001
- [x] SCN-SRC-001
- [x] SCN-GQ-001 (+ SCN-GQ-002 deferred)
- [x] SCN-GATE-001
