# ADR-007: BA Agent + CEO Feedback Loop

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 had 3 technical agents and human BA/DA feedback only via backlog. User acts as CEO reviewing team output.

## Decision

1. Add **Business Analyst** as 4th LangGraph agent — metric definitions, CEO narrative, KPI alignment
2. Replace single-agent router for Explore with **collaborative pipeline**: DE → Analyst → Scientist → BA
3. After discovery, each role generates 2–3 **insight briefs** for CEO review
4. CEO feedback stored per theme; injected into subsequent agent prompts
5. BA definitions require CEO validation before Trusted promotion (hybrid model)

## Consequences

- Longer latency per CEO question (4 agents sequential)
- Better multi-perspective output quality
- Feedback loop reduces repeated mistakes
