# ADR-005: Theme Discovery Pipeline

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 schema scan only listed table names. Agents guessed column names (e.g. `FKDAT`) causing SQL failures.

## Decision

When a user selects a theme, run an automated **Discovery Pipeline**:
1. Fetch `INFORMATION_SCHEMA.COLUMNS` for theme tables
2. Profile row counts and sample `TOP N` rows
3. Heuristic relationship detection (shared key columns)
4. Persist to `data/local/knowledge/themes/{theme_id}/discovery.json`
5. Inject column metadata into all agent prompts

Add SQL auto-retry (1 round) when Fabric returns invalid column errors.

## Consequences

- First theme selection takes longer (acceptable — quality over speed)
- Discovery cache reused until re-run
- Reduces hallucinated column names significantly
