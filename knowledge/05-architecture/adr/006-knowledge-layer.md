# ADR-006: Structured Knowledge Layer

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Trusted semantic JSON only stores promoted metrics. Users need pre-explore knowledge: field definitions, KPI targets, approved joins.

## Decision

Add three JSON stores under `data/local/knowledge/`:
- **glossary.json** — field/table business definitions
- **targets.json** — analysis goals and KPI targets per theme
- **relationships.json** — approved table joins

CRUD via REST API + Streamlit Knowledge panel. All agents read knowledge on every request.

Hybrid BA flow: AI drafts definitions from discovery → CEO edits/approves → optional promote to Trusted.

## Consequences

- Knowledge is human-curated; quality improves over time
- CEO can seed definitions before first explore question
