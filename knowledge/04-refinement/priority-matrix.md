# Priority Matrix — Phase 1 (MoSCoW)

**Date:** 2026-07-15  
**Derived from:** `knowledge/03-prd/prd.md`, `knowledge/05-architecture/phases/phase-1.md`

---

## Must Have (M1–M7 core)

| ID | Story | Milestone |
|----|-------|-----------|
| INFRA-1 | Fabric SP connector | M1 |
| INFRA-2 | SQL read-only guard | M1 |
| INFRA-3 | Fabric health endpoint | M1 |
| INFRA-4 | Native runtime config | M1 |
| STORE-1 | SQLite chat history | M2 |
| STORE-2 | JSON backlog store | M2 |
| STORE-3 | Semantic Trusted JSON | M2 |
| UI-1 | Explore/Trusted toggle | M3 |
| UI-3 | Backlog sidebar | M3 |
| UI-4 | Theme selection | M4 |
| EXPLORE-1 | Schema scan + 3 themes | M4 |
| EXPLORE-2 | Quality Bar D assembly | M5 |
| AGENT-1 | Agent prompt updates | M5 |
| HANDOFF-1 | Thai Markdown export | M6 |
| TRUST-1 | Trusted promotion HITL | M7 |

## Should Have

| ID | Story | Milestone |
|----|-------|-----------|
| UI-2 | Progress & agent status | M3 |
| VALID-1 | E2E validation run | M8 |

## Could Have (Phase 1 stretch)

| ID | Story | Notes |
|----|-------|-------|
| — | ODBC setup script for Windows | DX improvement |
| — | Sample theme cache after first scan | Avoid re-scan |

## Won't Have (Phase 1)

| Item | PRD ref |
|------|---------|
| Multi-user auth | NG1 |
| Auto-schedule/alerts | NG2 |
| ML training | NG3 |
| Fabric write-back | NG4 |
| UI redesign | NG5 |
| PostgreSQL runtime | NG6 |
| Cloud LLM | NG7 |

---

## Sprint Suggestion (Build Stage)

| Sprint | Focus | Stories |
|--------|-------|---------|
| Build-1 | Foundation | INFRA-1,2,3,4 |
| Build-2 | Storage | STORE-1,2,3 |
| Build-3 | UI + Modes | UI-1,2,3 |
| Build-4 | Explore core | EXPLORE-1, UI-4, AGENT-1 |
| Build-5 | Quality + Handoff | EXPLORE-2, HANDOFF-1 |
| Build-6 | Trusted + Validate | TRUST-1, VALID-1 |

*No fixed timeline — quality over speed.*
