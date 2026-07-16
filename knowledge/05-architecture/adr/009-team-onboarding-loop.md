# ADR-009: Team Onboarding Loop (Phase 2.5)

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 2 runs the 4-agent pipeline only when the CEO asks a question. The CEO wanted agents to learn the warehouse collaboratively **before** questions, maintain shared team memory, and apply feedback to role-owned knowledge stores.

## Decision

1. Add **onboarding graph** (DE → DA → DS → BA) triggered after theme discovery
2. Persist **team memory** per theme at `data/local/team_memory/{theme_id}.json`
3. Inject `team_memory_context` into all agent prompts via `prepare_context_node`
4. Add **feedback router** — CEO comments update glossary (DA), targets (BA), relationships (DE)
5. Keep briefings for CEO UI; onboarding is the deep baseline for chat

## Consequences

- First theme selection takes longer (discovery + onboarding LLM chain)
- Team memory must be re-run after major knowledge changes
- Feedback-routed items remain draft until approved in Knowledge panel
