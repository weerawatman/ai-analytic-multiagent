# Feasibility Assessment — AI Fabric Insight Explorer

**Date:** 2026-07-15  
**Status:** Reviewed — proceed to Design  
**Derived from:** `discovery-brief.md`, grill session, codebase inspection

---

## Executive Summary

**Verdict: FEASIBLE** for Phase 1 on owner's Windows machine with Fabric read-only access and local Ollama.

Primary risks are local LLM quality for heavy validation bar, SAP schema complexity, and refactor effort to remove PostgreSQL dependency — all acceptable given owner constraints (solo user, quality over speed).

---

## Technical Feasibility

| Area | Rating | Notes |
|------|--------|-------|
| Fabric SP connectivity | ✅ High | Owner has admin + SP credentials; standard ODBC/pyodbc path |
| Read-only SQL guard | ✅ High | Straightforward parser/allowlist in FastAPI service layer |
| LangGraph multi-agent | ✅ High | Already implemented in `backend/app/agents/` |
| HITL approval flow | ✅ High | LangGraph interrupt + `/api/v1/approval/` exists |
| Local Ollama ~14B–32B | ⚠️ Medium | 32GB RAM sufficient; quality/latency trade-off acceptable |
| Remove PostgreSQL | ⚠️ Medium | Requires refactor of `backend/app/db/` and chat routes |
| Schema theme scan (SAP) | ⚠️ Medium | Large DW — rank by metadata, not full profiling initially |
| Streamlit UI extensions | ✅ High | Minimal mode/backlog/export panels sufficient |

---

## Operational Feasibility

| Area | Rating | Notes |
|------|--------|-------|
| Solo Phase 1 user | ✅ High | No auth/multi-tenant complexity |
| BA/DA handoff offline | ✅ High | Markdown export + feedback fields |
| Data security (SAP PRD) | ✅ High | `data/local/` gitignore + localhost only |
| Native Windows runtime | ✅ High | Avoids Docker/Fabric networking issues |

---

## Economic / Effort Feasibility

| Item | Estimate |
|------|----------|
| Phase 1 milestones (M1–M8) | 8 work packages; no fixed deadline |
| Existing codebase reuse | ~60% infrastructure reusable (FastAPI, LangGraph, Streamlit, HITL) |
| New build areas | Fabric connector, SQL guard, JSON/SQLite storage, Explore/Trusted UX |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 14B model fails Quality Bar D | High | Switch to ~32B via env; accept slow runs |
| Fabric auth fails on Windows | High | Early M1 spike; document ODBC 18 setup |
| Definition drift persists if backlog unused | Medium | Phase 1 DoD requires ≥1 Trusted promotion |
| Scope creep to multi-user | Medium | PRD non-goals + stage gates |

---

## Go / No-Go Decision

| Decision | Owner | Date |
|----------|-------|------|
| **GO** — proceed to Design (Stage 02) | Data Engineer | 2026-07-15 |

---

## References

- `knowledge/01-discovery/discovery-brief.md`
- `knowledge/01-discovery/research/existing-codebase-assessment.md`
