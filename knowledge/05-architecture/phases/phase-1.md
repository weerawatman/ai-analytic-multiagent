# Phase 1 — Delivery Plan

**Goal:** Complete one full Explore → Trusted cycle on one Fabric theme  
**Owner:** Solo Data Engineer  
**Target:** No fixed deadline — quality over speed

---

## Milestones

### M1: Foundation & Fabric Connect
**Deliverables:**
- Fabric connector with Service Principal auth
- SQL guard (SELECT-only)
- Health check endpoint
- `.env` template updated for Fabric vars
- Remove PostgreSQL from runtime path

**Backlog items:** INFRA-1, INFRA-2, INFRA-3  
**DoD:** AC-1 passes

---

### M2: Local Storage Refactor
**Deliverables:**
- `data/local/` + `data/templates/` structure
- SQLite chat store
- JSON backlog store
- `.gitignore` for `data/local/`
- Template JSON files

**Backlog items:** STORE-1, STORE-2  
**DoD:** AC-9, AC-10 pass

---

### M3: Explore/Trusted Mode & UI
**Deliverables:**
- Mode toggle in Streamlit
- Draft labeling on Explore outputs
- Theme selection UI
- Progress indicator for long agent runs

**Backlog items:** UI-1, UI-2  
**DoD:** AC-3 partial

---

### M4: Schema Scan & Theme Proposal
**Deliverables:**
- DE agent schema introspection against Fabric
- Theme ranking logic
- Present 3 themes in Thai

**Backlog items:** EXPLORE-1  
**DoD:** AC-2 passes

---

### M5: Quality Bar D Pipeline
**Deliverables:**
- Multi-agent Explore with assumption challenges
- Quality assembly step before backlog save
- Backlog save with full schema fields

**Backlog items:** EXPLORE-2, AGENT-1  
**DoD:** AC-4 passes

---

### M6: Handoff & Feedback Loop
**Deliverables:**
- Markdown export (Thai)
- BA/DA feedback capture in UI
- Status lifecycle on backlog items

**Backlog items:** HANDOFF-1  
**DoD:** AC-5, AC-6 pass

---

### M7: Trusted Promotion
**Deliverables:**
- HITL preview for Trusted entry
- Semantic JSON write on approval
- Trusted mode queries using approved definitions

**Backlog items:** TRUST-1  
**DoD:** AC-7, AC-8 pass

---

### M8: Phase 1 Validation
**Deliverables:**
- Run full cycle on chosen theme
- Document results in backlog
- Owner sign-off

**DoD:** PRD Phase 1 Definition of Done checklist complete

---

## Dependencies

```
M1 ──► M2 ──► M3
         │
M1 ──► M4 ──► M5 ──► M6 ──► M7 ──► M8
```

---

## Risks

| Risk | Mitigation |
|------|------------|
| Local 14B insufficient for Quality Bar D | Switch to ~32B via env; accept latency |
| Fabric SP auth complexity on Windows | Test early in M1; document driver setup |
| SAP schema too large for theme scan | Sample + rank by table metadata/stats |
| Ollama timeout on long analyses | Increase timeout; show progress in UI |

---

## Out of Scope (This Phase)

See PRD Non-Goals.
