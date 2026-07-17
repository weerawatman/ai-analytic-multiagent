# AGENTS.md — Universal Agent Contract

This file defines how AI agents should interact with this repository.

---

## Project Configuration

```
Project:     AI Analytics Multi-Agent (Fabric Insight Explorer)
Description: Local AI Data Team for deep insight exploration on Microsoft Fabric DW, with Explore/Trusted knowledge loop
Status:      build
Created:     2026-07-15
Updated:     2026-07-18
Owner:       Data Engineer (solo Phase 1)
```

**Status** reflects current focus. Valid values: `discovery`, `design`, `prd`, `refinement`, `architecture`, `build`, `testing`, `deployment`, `operations`.

---

## General Rules

1. **Read before you write.** Check `knowledge/` before producing artifacts.
2. **Respect preconditions.** Do not skip stages without required artifacts.
3. **Write artifacts to the correct location.** See stage definitions below.
4. **Flag human gates.** Stop and ask before scope, architecture, or production decisions.
5. **Maintain context chain.** Reference upstream artifacts (discovery → PRD → architecture).
6. **Phase 1 priority:** Output quality and correctness over speed or UI polish.
7. **Fabric is read-only.** Never execute write DDL/DML against `WH_SAP_PRD` without explicit human approval.

---

## Key Artifacts (Current)

| Stage | Artifact | Path |
|-------|----------|------|
| Discovery | Discovery brief | `knowledge/01-discovery/discovery-brief.md` |
| Design | User journeys | `knowledge/02-design/user-journeys/` |
| Design | Design decisions | `knowledge/02-design/design-decisions.md` |
| PRD | Product requirements | `knowledge/03-prd/prd.md` |
| PRD | Constraints | `knowledge/03-prd/constraints.md` |
| PRD | NFRs | `knowledge/03-prd/nfr.md` |
| Architecture | System design | `knowledge/05-architecture/architecture/Architecture.md` |
| Architecture | Tech stack | `knowledge/05-architecture/tech-stack.md` |
| Architecture | Phase 1 plan | `knowledge/05-architecture/phases/phase-1.md` |
| Architecture | **Roadmap G→K (self-learning analytics)** | `knowledge/05-architecture/phases/phase-g-to-k-grand-roadmap.md` |
| Architecture | Phase gates (audit trail) | `knowledge/05-architecture/phases/gates/` |
| Architecture | ADRs | `knowledge/05-architecture/adr/` |

---

## Phase 1 Summary (Locked Decisions)

- **Users:** Solo Data Engineer (BA/DA later)
- **Data source:** Microsoft Fabric DW primary; since Phase F a PostgreSQL WH_Silver mirror is a **labeled auto-fallback** (never silent — provenance on every result; see `phases/phase-f-postgres-fallback.md`)
- **Auth to DW:** Service Principal, SELECT-only + SQL allowlist guard
- **Modes:** `Explore` (draft) and `Trusted` (validated definitions)
- **Quality bar:** Heavy validation (SQL, assumptions, sanity checks, sample rows)
- **Storage:** JSON (semantic/backlog) + SQLite (chat history) under `data/local/`
- **Runtime:** Native on Windows (FastAPI + Streamlit + Ollama)
- **LLM:** Local Ollama ~14B default, switchable to ~32B
- **Language:** Thai for UI/reports; English for SQL/technical metadata
- **Phase 1 done when:** One theme completes full loop + at least one Trusted playbook

---

## Phase G–K Delegation Rules (binding for any AI implementing the roadmap)

Before implementing **any** part of phases G–K (self-learning analytics), you MUST:

1. Read `knowledge/05-architecture/phases/phase-g-to-k-grand-roadmap.md` **§4 Delegation Guardrails** in full, and follow its Handoff Protocol (§4.4): create a phase doc from `phases/_TEMPLATE-phase.md` before writing any code.
2. Treat `backend/tests/test_roadmap_conformance.py` as a **binding contract** — it enforces the roadmap invariants automatically (skipped until each module exists, then enforced forever). Never weaken, skip, or delete these tests to make a build pass.
3. Any deviation from locked decisions or canonical names requires **owner approval first**, recorded in the phase doc's Deviation Log — never "do first, report later".
4. A phase is only "done" when its gate artifact exists in `phases/gates/` with real evidence (see `gates/README.md`).

---

## Human Gates

| Gate | When |
|------|------|
| PRD sign-off | Before refinement/build |
| Architecture sign-off | Before build sprint |
| Trusted promotion | Before insight enters semantic layer |
| DW change suggestions | Before any write to Fabric (Phase 1: never auto-apply) |

---

## Feedback Loop

```
Explore → Backlog → BA/DA validation → Trusted semantic/playbook → future Explore
```

Operations feedback (Phase 2+) feeds back into `knowledge/01-discovery/`.
