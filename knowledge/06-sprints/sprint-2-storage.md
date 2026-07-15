# Build Sprint 2 — Local Storage (SQLite + JSON)

**Stage:** 06 Build  
**Date:** 2026-07-15  
**Stories:** STORE-1, STORE-2, STORE-3  
**Status:** Complete — pending commit sign-off

---

## Delivered

| Story | Implementation |
|-------|----------------|
| STORE-1 | `chat_store.py` — SQLite sessions/messages in `data/local/app.db` |
| STORE-2 | `backlog_store.py` + `api/routes/backlog.py` — JSON per item |
| STORE-3 | Refactored `semantic_store.py` — `trusted.json` / `draft.json` + promote |

## Supporting

- `local_paths.py` — auto-create `data/local/{backlog,semantic,exports,samples}`
- `api/routes/sessions.py` — list sessions, get messages
- `api/routes/semantic.py` — GET trusted/draft
- Chat route persists user/assistant messages to SQLite
- App lifespan initializes local storage on startup

## API Endpoints Added

| Method | Path |
|--------|------|
| GET | `/api/v1/sessions/` |
| GET | `/api/v1/sessions/{id}/messages` |
| GET/POST | `/api/v1/backlog/` |
| GET/PATCH | `/api/v1/backlog/{id}` |
| GET | `/api/v1/semantic/trusted` |
| GET | `/api/v1/semantic/draft` |

## Tests

- `test_storage.py` — unit tests for stores
- `test_backlog_api.py` — API integration tests

## AC Coverage

- AC-9: Chat/backlog/semantic work without PostgreSQL
- AC-10: `data/local/` remains gitignored

## Next Sprint

Build Sprint 3 — UI-1, UI-2, UI-3 (Explore/Trusted toggle, progress, backlog sidebar)
