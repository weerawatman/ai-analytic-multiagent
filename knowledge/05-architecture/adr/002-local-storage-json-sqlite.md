# ADR-002: JSON + SQLite Local Storage (No PostgreSQL)

## Status: Accepted

## Context

The existing codebase uses PostgreSQL for chat/conversation storage and ships dummy analytics data. The owner wants to focus exclusively on Fabric for business data and avoid multiple storage paths in Phase 1.

## Decision

- **Remove PostgreSQL from Phase 1 runtime path**
- Store insight backlog and semantic/Trusted definitions as **JSON files**
- Store chat session history in **SQLite** (`data/local/app.db`)
- Separate committable templates (`data/templates/`) from sensitive local data (`data/local/` gitignored)

## Consequences

**Easier:**
- Single analytics source (Fabric)
- Simple backup (copy `data/local/`)
- JSON diffs readable for Trusted promotion review

**Harder:**
- Refactor existing SQLAlchemy/Postgres code
- JSON lacks concurrent write safety (acceptable for solo user)
- No relational queries across backlog without loading files

## References

- PRD FR-6, FR-7, FR-8
- Constraints TC-7, TC-8
