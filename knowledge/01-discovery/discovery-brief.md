# Discovery Brief — AI Fabric Insight Explorer

**Date:** 2026-07-15  
**Status:** Validated (grill session + human confirm)  
**Source:** Structured decision interview with project owner

---

## Problem Statement

A small internal data team (Data Engineer + Business Analysts + Data Analysts, ≤10 people) suffers from:

1. **Definition drift** — metrics, SQL, and business terms mean different things to different people
2. **Handoff friction** — DE ↔ BA/DA lose context when passing schema, queries, and assumptions

Current analytics practices are legacy-oriented. The team needs a way to **continuously improve how insights are discovered and validated**, not just answer one-off questions faster.

---

## Target Users

| Phase | Users |
|-------|-------|
| Phase 1 | Solo Data Engineer (project owner) |
| Phase 2+ | BA, DA, full data team (≤10) |

---

## Proposed Solution (High Level)

A **local AI Data Team** (LangGraph multi-agent) connected to **Microsoft Fabric Data Warehouse** that:

- Explores data broadly in `Explore` mode (draft insights)
- Validates deeply before saving candidates (heavy quality bar)
- Captures insight candidates in a structured backlog
- Supports handoff to BA/DA with exportable reports
- Promotes validated definitions to `Trusted` semantic layer + playbook

---

## Why Now / Why Worth Building

- Existing repo already has LangGraph orchestrator, 3 agents, HITL, Streamlit UI
- Owner has admin access to `WH_SAP_PRD` via Service Principal
- Owner accepts slow, thorough analysis on local hardware (32GB RAM, Ollama)
- No starter business questions yet — system must help **discover** themes and questions from schema first

---

## Feasibility Notes

| Factor | Assessment |
|--------|------------|
| Fabric connectivity | Feasible — SP auth, read-only |
| Local LLM quality | Feasible with ~14B–32B; latency acceptable |
| No PostgreSQL | Requires refactor of current DB-backed chat storage |
| Solo Phase 1 | Reduces auth/multi-user complexity |
| SAP DW complexity | High — schema scan + theme proposal needed before deep dive |

---

## Success Signal (Phase 1)

Complete one full theme cycle:

```
Connect Fabric → Scan schema → Pick theme → Explore → Backlog →
Talk to BA/DA → Record feedback → Promote ≥1 Trusted definition + playbook
```

---

## References

- Shared understanding confirmed: 2026-07-15
- Upstream repo: [agentic-engineering-starter-pack](https://github.com/tngwilkins/agentic-engineering-starter-pack)
