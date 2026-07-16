# Phase 2.5 — Team Onboarding Loop

**Goal:** Before the CEO asks questions, all 4 agents onboard on the theme — shared team memory, role handoffs, and feedback routed to owned stores.

**Status:** build  
**Depends on:** Phase 2 (discovery, knowledge, collaborative graph, CEO loop)

---

## What Phase 2.5 Adds

### M14: Team Onboarding Graph
- After discovery, run **DE → DA → DS → BA** onboarding pipeline (no user question)
- Each role produces a **handoff summary** + structured **artifact**
- Persist to `data/local/team_memory/{theme_id}.json`

### M15: Team Memory in Chat
- `format_team_memory_context()` injected via `prepare_context_node`
- All 4 agents see onboarding baseline + prior CEO feedback per role

### M16: Feedback Router
- CEO approve/reject/comment → role-owned updates:
  - **DE** → `relationships.json`
  - **DA** → `glossary.json`
  - **BA** → `targets.json`
- Always logged in team memory `feedback_notes`

---

## Flow

```
เลือก Theme
  → Discovery (profile columns)
  → Briefings (CEO panel — optional quick briefs)
  → Onboarding graph (DE→DA→DS→BA) → team_memory.json
CEO ถามคำถาม
  → prepare_context (discovery + knowledge + sql_ref + team_memory + feedback)
  → collaborative answer graph
CEO ให้ feedback
  → feedback.json + feedback_router → knowledge stores + team_memory notes
```

---

## Storage

```
data/local/team_memory/
  {theme_id}.json
```

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/onboarding/{theme_id}` | Load team memory |
| POST | `/api/v1/onboarding/{theme_id}/run?theme_name=` | Run onboarding |
| POST | `/api/v1/feedback/{theme_id}?theme_name=` | Feedback + route to stores |

---

## Human Gates

- Onboarding uses LLM — review Team Memory panel before trusting answers
- Feedback-routed glossary/targets remain **draft** until approved in Knowledge panel
- Re-run onboarding after major glossary/relationship changes

---

## Phase 2.5 Done When

- [ ] Select theme → onboarding completes → Team Memory panel shows 4 role handoffs
- [ ] Chat injects team memory context
- [ ] CEO feedback on DA brief updates glossary (visible in Knowledge panel)
- [ ] pytest includes team_memory + feedback_router tests
