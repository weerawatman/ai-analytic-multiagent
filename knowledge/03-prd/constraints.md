# Constraints — Phase 1

**Derived from:** Discovery brief + grill session (2026-07-15)

---

## Technical Constraints

| ID | Constraint |
|----|------------|
| TC-1 | **Must** connect to Microsoft Fabric Data Warehouse (`WH_SAP_PRD`) |
| TC-2 | **Must** use Service Principal authentication (Entra ID) for runtime |
| TC-3 | **Must** enforce read-only SQL (SELECT-only + allowlist guard) |
| TC-4 | **Must not** write to Fabric DW automatically — suggest only, human confirms |
| TC-5 | **Must** run natively on Windows (no Docker for Phase 1 runtime) |
| TC-6 | **Must** use local Ollama only — no cloud LLM API |
| TC-7 | **Must not** use PostgreSQL for analytics or app state in Phase 1 |
| TC-8 | **Must** store state locally: JSON (backlog/semantic) + SQLite (chat) |
| TC-9 | **Must** retain LangGraph + FastAPI + Streamlit stack (extend, not rewrite) |
| TC-10 | Ollama model: start ~14B, configurable switch to ~32B via env |

---

## Business Constraints

| ID | Constraint |
|----|------------|
| BC-1 | Phase 1 user: solo Data Engineer only |
| BC-2 | BA/DA interaction happens outside system or via feedback fields — no login |
| BC-3 | Priority is **output depth and correctness**, not speed or UI polish |
| BC-4 | Production SAP data — local artifacts must not leak to git |
| BC-5 | Thai language for user-facing reports; English for SQL and technical keys |

---

## Integration Constraints

| ID | Constraint |
|----|------------|
| IC-1 | Fabric is the **only** business data source in Phase 1 |
| IC-2 | Ollama runs on localhost (default `http://localhost:11434`) |
| IC-3 | Existing HITL approval flow must extend to Trusted promotion |
| IC-4 | `.env` holds secrets — never committed |

---

## Compliance / Security Constraints

| ID | Constraint |
|----|------------|
| SC-1 | `data/local/` gitignored — contains query results and chat with business data |
| SC-2 | `data/templates/` may be committed — no real data |
| SC-3 | No authentication on Streamlit Phase 1 (localhost only) |
| SC-4 | Do not expose FastAPI/Streamlit ports beyond local machine |

---

## Out of Scope (Hard Boundary)

See PRD Non-Goals NG1–NG8.
