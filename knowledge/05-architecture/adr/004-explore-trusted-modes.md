# ADR-004: Explore vs Trusted Dual Modes

## Status: Accepted

## Context

The owner has no predefined business questions and needs broad schema exploration first. However, the primary problem is definition drift — Explore outputs must not be mistaken for validated team definitions. BA/DA validation happens outside or via feedback fields in Phase 1.

## Decision

Implement two explicit modes:

| Mode | Purpose | Output label |
|------|---------|--------------|
| **Explore** | Broad discovery, theme-based questioning, heavy quality bar | Draft — รอ validate |
| **Trusted** | Queries using human-approved semantic definitions | Trusted |

- Explore uses full warehouse read access
- Trusted references only promoted semantic entries
- Promotion requires HITL approval after BA/DA feedback

## Consequences

**Easier:**
- Prevents false confidence from draft SQL
- Clear handoff workflow to BA/DA
- Supports continuous improvement loop

**Harder:**
- UI must always show current mode
- Two code paths for query generation
- Trusted layer empty until first promotion completes

## References

- PRD FR-3, FR-4
- Discovery brief: definition drift problem
