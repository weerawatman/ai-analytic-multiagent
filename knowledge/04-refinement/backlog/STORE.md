# STORE-1: SQLite Chat History

**Epic:** M2 Local Storage  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-9

## User Story
As a Data Engineer, I want chat history persisted locally so that I can resume exploration sessions.

## Tasks
- [ ] Create SQLite schema: sessions, messages
- [ ] Replace PostgreSQL conversation model with SQLite store
- [ ] Migrate chat API routes to use SQLite
- [ ] Remove Postgres dependency from startup path

## Acceptance
- Given a chat session, When app restarts, Then messages are still available

---

# STORE-2: JSON Backlog Store

**Epic:** M2 Local Storage  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-4, AC-10

## User Story
As a Data Engineer, I want insight candidates saved as JSON files so that I can review and diff them.

## Tasks
- [ ] Implement `BacklogStore` service (CRUD on `data/local/backlog/`)
- [ ] Pydantic model matching template schema
- [ ] API routes: list, get, create, patch
- [ ] Auto-create `data/local/` on first run

## Acceptance
- Given saved candidate, When file read, Then all Quality Bar D fields present

---

# STORE-3: Semantic / Trusted JSON Store

**Epic:** M2 Local Storage  
**Priority:** Must  
**Estimate:** S  
**AC:** AC-7, AC-8

## User Story
As a Data Engineer, I want Trusted definitions in JSON so that Trusted mode can reference them.

## Tasks
- [ ] Refactor `semantic_store.py` for `data/local/semantic/trusted.json`
- [ ] Keep templates in `data/templates/`
- [ ] Promotion writes approved entry atomically

## Acceptance
- Given approved promotion, When Trusted mode query, Then metric appears in loaded definitions
