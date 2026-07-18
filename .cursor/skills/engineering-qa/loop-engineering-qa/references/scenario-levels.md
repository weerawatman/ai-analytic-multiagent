# Scenario levels

| Level | Name | What runs | Needs |
|-------|------|-----------|-------|
| **L0** | Env smoke | `start.ps1 -Status`, Ollama tags, optional 1-token generate | Network local |
| **L1** | Offline suite | `pytest backend/tests -q` + focus on `test_roadmap_conformance.py` | `.venv`, no live Fabric required |
| **L2** | Live / semi-live | Quality chat scripts, golden eval, data-source scenarios | Backend up, Ollama model loadable, Fabric and/or Postgres |
| **L3** | Manual UI | Streamlit checklist (human or future Playwright) | Frontend :8501 |
| **Human** | Owner gates | Trusted, KPI formulas, production sign-off | Owner |

## Mapping to SCN groups

See [`scenario-catalog.md`](../../../../knowledge/07-testing/loop-engineering/scenario-catalog.md).

| Group | Default level |
|-------|---------------|
| `env-smoke` | L0 |
| `offline-unit` | L1 |
| `conformance` | L1 |
| `agent-pipeline` | L2 |
| `ollama-failure` | L0 then L2 |
| `data-source` | L2 |
| `golden` | L2 (harness-only until live `answer_fn` wired) |
| `owner-gate` | Human |

## Default when user says "ความพร้อมก่อนทดสอบจริง"

Run **L0 + L1**. Only escalate to L2 if L0/L1 are green **and** user wants live chat verification.
