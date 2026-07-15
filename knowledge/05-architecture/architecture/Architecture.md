# Architecture — AI Fabric Insight Explorer

**Version:** 1.0  
**Date:** 2026-07-15  
**Status:** Signed off — 2026-07-15  
**Derived from:** `knowledge/03-prd/prd.md`, `constraints.md`, `nfr.md`

---

## System Overview

Local multi-agent analytics assistant that reads from **Microsoft Fabric DW**, produces deep draft insights in **Explore** mode, and promotes validated knowledge to **Trusted** semantic definitions after human approval.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Windows Local Machine                           │
│                                                                         │
│  ┌──────────────┐    HTTP     ┌──────────────┐    LangGraph            │
│  │  Streamlit   │ ──────────► │   FastAPI    │ ──────────► Orchestrator │
│  │  UI (TH)     │ ◄────────── │   Backend    │ ◄────────── 3 Agents    │
│  └──────────────┘             └──────┬───────┘                         │
│         │                             │                                 │
│         │                             ├──► Ollama (~14B / ~32B)         │
│         │                             │                                 │
│         │                             ├──► SQL Guard (SELECT-only)      │
│         │                             │         │                       │
│         │                             │         ▼                       │
│         │                             │    Fabric DW (WH_SAP_PRD)       │
│         │                             │    [Service Principal]          │
│         │                             │                                 │
│         │                             ├──► Local State                  │
│         │                             │    ├─ JSON: backlog, semantic    │
│         │                             │    └─ SQLite: chat sessions      │
│         │                             │         (data/local/)            │
│         └─────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Streamlit UI** | Mode toggle (Explore/Trusted), theme picker, chat, backlog view, export, HITL approval panels |
| **FastAPI** | REST API, session management, Fabric query execution, SQL guard, file I/O |
| **LangGraph Orchestrator** | Route to DE / Analyst / Scientist; approval interrupts |
| **Data Engineer Agent** | Schema introspection, semantic layer proposals, theme scanning |
| **Data Analyst Agent** | SQL generation, result interpretation, pattern detection |
| **Data Scientist Agent** | Alternative angles, assumption challenges, analytical suggestions |
| **SQL Guard** | Parse/validate agent SQL before execution — SELECT-only allowlist |
| **Fabric Connector** | SP auth, connection pooling, query execution, metadata scan |
| **Backlog Store** | JSON files for insight candidates and status lifecycle |
| **Semantic Store** | JSON Trusted definitions + templates |
| **Chat Store** | SQLite for conversation history and session metadata |
| **Report Generator** | Markdown export (Thai) for BA/DA handoff |

---

## Data Flow — Explore Mode

```
1. User triggers schema scan (or first run)
2. DE Agent queries INFORMATION_SCHEMA → proposes 3 themes
3. User selects theme
4. Orchestrator routes exploration questions
   ├── Analyst: primary SQL + results
   ├── Scientist: alternative check / challenge assumptions
   └── DE: schema context + semantic gaps
5. Quality Bar D assembly → candidate payload
6. User saves to backlog (JSON)
7. Optional: export Thai report → discuss with BA/DA offline
8. User records feedback → status update
9. HITL approval → promote to Trusted semantic JSON
```

---

## Data Flow — Trusted Mode

```
1. User asks question in Trusted mode
2. System loads Trusted definitions for theme/metrics
3. Analyst generates SQL constrained to approved definitions
4. Output labeled Trusted (not draft)
5. Conflicts with draft assumptions flagged explicitly
```

---

## Storage Model

### Directory Layout

```
data/
├── templates/              # Committable — structure only, no real data
│   ├── semantic_layer.template.json
│   └── backlog_item.template.json
└── local/                  # GITIGNORE — production query results
    ├── app.db              # SQLite: chat sessions, messages
    ├── backlog/            # JSON per insight candidate
    │   └── {uuid}.json
    ├── semantic/
    │   ├── trusted.json    # Promoted definitions
    │   └── draft.json      # In-progress semantic proposals
    └── exports/            # Generated handoff reports (.md)
```

### Backlog Item Schema (JSON)

```json
{
  "id": "uuid",
  "theme": "string",
  "mode": "explore",
  "question_th": "string",
  "answer_summary_th": "string",
  "sql_primary": "string",
  "sql_alternative": "string",
  "assumptions": ["string"],
  "confidence": "high|medium|low",
  "unknowns": ["string"],
  "questions_for_ba_da": ["string"],
  "sample_data_ref": "path or inline summary",
  "status": "new|discussing|validated|rejected|promoted",
  "ba_da_feedback": [{"at": "iso8601", "note": "string"}],
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

### Trusted Definition Schema (JSON)

```json
{
  "metric_key": "snake_case_english",
  "display_name_th": "string",
  "business_definition_th": "string",
  "sql_template": "string",
  "grain": "string",
  "standard_filters": ["string"],
  "validated_assumptions": ["string"],
  "playbook_th": "string",
  "example_questions_th": ["string"],
  "source_backlog_id": "uuid",
  "approved_at": "iso8601",
  "approved_by": "string"
}
```

---

## Integration Points

| System | Direction | Protocol | Auth |
|--------|-----------|----------|------|
| Microsoft Fabric DW | Read | TDS/SQL (pyodbc or ODBC 18) | Service Principal |
| Ollama | Local | HTTP REST | None |
| File system | Local | JSON + SQLite | OS permissions |

**Phase 1 removes:** PostgreSQL, Docker Compose runtime dependency

---

## Agent Graph (LangGraph)

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         ▼
                    ┌─────────┐
                    │ Router  │
                    └────┬────┘
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │ Data       │ │ Data       │ │ Data       │
    │ Engineer   │ │ Analyst    │ │ Scientist  │
    └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
          │              │              │
          └──────────────┼──────────────┘
                         ▼
              ┌─────────────────────┐
              │ Quality Assembly    │  (Explore only)
              │ + Backlog Candidate │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │ HITL Gate           │  (semantic / promote)
              │ [interrupt]         │
              └──────────┬──────────┘
                         ▼
                    ┌─────────┐
                    │   END   │
                    └─────────┘
```

---

## SQL Guard Design

```
Input: agent-generated SQL string
  │
  ├─ Normalize (strip comments, whitespace)
  ├─ Blocklist check (INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, EXEC, TRUNCATE, MERGE...)
  ├─ Allowlist: must start with SELECT or WITH (CTE)
  ├─ Optional: single-statement enforcement
  └─ Pass → execute via Fabric connector
       Fail → return error to agent for revision (no execution)
```

---

## Security Architecture

| Layer | Control |
|-------|---------|
| Fabric | SP with read-only DW permissions (principle of least privilege recommended) |
| Application | SQL guard before any execution |
| Secrets | `.env` only — never in git |
| Data at rest | `data/local/` gitignored |
| Network | Bind to localhost; no auth Phase 1 (single user) |
| HITL | All Trusted promotions and DW change suggestions require human click |

---

## Migration from Current Codebase

| Current | Phase 1 Target |
|---------|----------------|
| PostgreSQL chat storage | SQLite `data/local/app.db` |
| `data/semantic_layer.json` | `data/local/semantic/` + templates |
| Docker Compose runtime | Native Windows scripts |
| `qwen2.5-coder:7b` default | Configurable ~14B default |
| Dummy `init.sql` analytics | Removed from analysis path |
| Single chat mode | Explore + Trusted modes |

---

## Phase 2 Extension Points (Not Built Now)

- Multi-user auth (Entra ID or simple team login)
- BA/DA read-only UI for feedback
- Fabric write-back pipeline (human-triggered)
- Scheduled re-exploration jobs
- Docker packaging for team deployment

---

## ADRs

| ADR | Title |
|-----|-------|
| [001](adr/001-fabric-read-only.md) | Fabric read-only via Service Principal |
| [002](adr/002-local-storage-json-sqlite.md) | JSON + SQLite local storage |
| [003](adr/003-native-runtime-no-docker.md) | Native Windows runtime |
| [004](adr/004-explore-trusted-modes.md) | Explore vs Trusted dual modes |

---

## Human Gate

- [x] Architecture reviewed by project owner
- [x] ADRs accepted
- [x] Storage and security model agreed

**Sign-off:** Data Engineer (owner) — 2026-07-15
