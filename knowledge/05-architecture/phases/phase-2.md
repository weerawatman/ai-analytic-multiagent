# Phase 2 — Autonomous Data Team + CEO Loop + Knowledge

**Goal:** Proactive data discovery, multi-role briefing, CEO feedback loop, and structured knowledge layer.

**Status:** build  
**Depends on:** Phase 1 complete (Explore → Trusted cycle)

---

## Milestones

### M9: Theme Discovery Pipeline
- Column profiling + sample rows per theme table
- Schema context pack injected into agent prompts
- SQL auto-retry on invalid column errors

### M10: Knowledge Layer
- Glossary, targets, relationships JSON stores
- CRUD API + Streamlit Knowledge panel

### M11: BA Agent + Collaborative Graph
- Business Analyst agent (hybrid — AI drafts, CEO validates)
- Explore pipeline: DE → Analyst → Scientist → BA → Quality

### M12: CEO Briefing + Feedback
- Role briefs after discovery
- CEO approve/reject/comment → feedback store
- Feedback injected into subsequent agent runs

### M13: Phase 2 Validation
- Extended validator, tests, sign-off doc

---

## ADRs

| ADR | Topic |
|-----|-------|
| [005](../adr/005-theme-discovery-pipeline.md) | Theme discovery pipeline |
| [006](../adr/006-knowledge-layer.md) | Knowledge layer (glossary/targets) |
| [007](../adr/007-ba-agent-ceo-loop.md) | BA agent + CEO feedback loop |

---

## Storage Layout (Phase 2)

```
data/local/knowledge/
  glossary.json
  targets.json
  relationships.json
  themes/{theme_id}/discovery.json
data/local/feedback/
  {theme_id}.json
data/local/briefings/
  {theme_id}.json
```

---

## Human Gates

- CEO validates all BA definitions before Trusted promotion
- Fabric remains read-only
- No cloud LLM (local Ollama only)
