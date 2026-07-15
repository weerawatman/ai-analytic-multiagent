# Research — Existing Codebase Assessment

**Date:** 2026-07-15  
**Purpose:** Validate discovery assumptions against current repo state

---

## Current Stack (As-Is)

| Component | Location | Phase 1 fate |
|-----------|----------|--------------|
| FastAPI backend | `backend/app/main.py` | **Keep** — extend |
| LangGraph orchestrator | `backend/app/agents/orchestrator.py` | **Keep** — extend modes |
| 3 agents (DE/Analyst/Scientist) | `backend/app/agents/*.py` | **Keep** — extend prompts |
| HITL approval | `backend/app/api/routes/approval.py` | **Keep** — extend for Trusted |
| Streamlit UI | `frontend/app.py` | **Keep** — minimal extensions |
| PostgreSQL + SQLAlchemy | `backend/app/db/` | **Remove from runtime** |
| Dummy data `init.sql` | `data/init.sql` | **Remove from analysis path** |
| Semantic layer file | `data/semantic_layer.json` | **Migrate** to `data/local/semantic/` |
| Docker Compose | `docker-compose.yml` | **Not used** Phase 1 runtime |
| Ollama 7B default | `backend/app/core/config.py` | **Change** to ~14B configurable |

---

## Reusable Patterns

1. **Router node** — routes user message to specialist agent
2. **Approval interrupt** — LangGraph pauses for human decision on semantic changes
3. **Semantic store service** — `backend/app/services/semantic_store.py` — adapt for JSON local storage
4. **Chat API** — `backend/app/api/routes/chat.py` — extend with `mode` parameter

---

## Gap Analysis (Build Required)

| Gap | Priority |
|-----|----------|
| Fabric connector + SP auth | P0 |
| SQL read-only guard | P0 |
| SQLite chat store | P0 |
| JSON backlog store | P0 |
| Explore/Trusted mode in UI + API | P0 |
| Schema scan + theme proposal | P1 |
| Quality Bar D assembly pipeline | P1 |
| Thai Markdown export | P1 |
| BA/DA feedback capture | P1 |
| Trusted promotion flow | P1 |

---

## Comparable Approaches Considered

| Approach | Why not chosen (Phase 1) |
|----------|--------------------------|
| Cloud LLM (GPT/Claude) | Owner constraint: local only |
| PostgreSQL mirror of Fabric | Adds dual path; owner wants Fabric only |
| Full UI redesign | Out of scope; quality over UX |
| Power BI / Fabric notebook only | Doesn't solve definition drift / backlog loop |

---

## Conclusion

Existing repo is a ** viable foundation**. Phase 1 is primarily **integration + workflow extension**, not greenfield build.
