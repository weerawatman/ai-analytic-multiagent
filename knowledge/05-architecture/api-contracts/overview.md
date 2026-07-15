# API Contracts — Overview

**Backend base:** `http://127.0.0.1:8000`  
**Version:** v1 (existing prefix `/api/v1`)

---

## Existing Endpoints (To Extend)

| Method | Path | Description | Phase 1 Changes |
|--------|------|-------------|-----------------|
| POST | `/api/v1/chat/` | Send message to AI team | Add `mode`, `theme_id` params |
| POST | `/api/v1/approval/` | Approve/reject proposals | Extend for Trusted promotion |
| GET | `/health` | Health check | Add Fabric connectivity status |

---

## New Endpoints (Phase 1)

### Schema & Themes

```
GET /api/v1/fabric/health
→ { "connected": true, "database": "WH_SAP_PRD" }

POST /api/v1/themes/scan
→ { "themes": [{ "id", "name_th", "rationale_th", "table_count", "starter_questions_th" }] }

GET /api/v1/themes/
→ List cached theme proposals
```

### Backlog

```
GET /api/v1/backlog/
→ List insight candidates (filter by status, theme)

GET /api/v1/backlog/{id}
→ Single backlog item

POST /api/v1/backlog/
→ Save new candidate (Quality Bar D payload)

PATCH /api/v1/backlog/{id}
→ Update status, add BA/DA feedback

POST /api/v1/backlog/{id}/export
→ Generate Thai Markdown report → returns path or content
```

### Trusted / Semantic

```
GET /api/v1/semantic/trusted
→ List Trusted definitions

POST /api/v1/semantic/promote
→ Request promotion (triggers HITL preview)

POST /api/v1/approval/trusted
→ Approve/reject Trusted promotion (extends approval)
```

### Chat Sessions

```
GET /api/v1/sessions/
→ List chat sessions (SQLite)

GET /api/v1/sessions/{id}/messages
→ Session message history
```

---

## Request/Response Notes

- All user-facing text fields support Thai (`*_th` suffix where bilingual)
- SQL fields always English
- `mode` enum: `explore` | `trusted`
- Errors return `{ "detail": "...", "detail_th": "..." }` where applicable

---

## SQL Execution (Internal — Not Public)

Fabric queries executed only through internal service after SQL guard — not exposed as raw endpoint to prevent bypass.
