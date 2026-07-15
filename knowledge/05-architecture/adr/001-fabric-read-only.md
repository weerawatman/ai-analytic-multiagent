# ADR-001: Fabric Read-Only via Service Principal

## Status: Accepted

## Context

Phase 1 requires direct access to Microsoft Fabric Data Warehouse (`WH_SAP_PRD`) containing production SAP data. The system must analyze data deeply but must not modify the warehouse. The owner is a Fabric admin with Service Principal credentials configured.

## Decision

- Connect to Fabric using **Entra ID Service Principal** (not personal SQL credentials)
- Enforce **SELECT-only** SQL via application-level guard before execution
- Agent may **suggest** DW changes (views, definitions) but **never auto-apply**
- Full read access within SP permissions — no table allowlist in Phase 1 (Explore discovery phase)

## Consequences

**Easier:**
- Clear audit identity (app, not person)
- Aligns with production data governance
- Supports future team deployment with same SP

**Harder:**
- SP permission setup required on Fabric workspace
- ODBC/driver configuration on Windows
- Must implement robust SQL guard to prevent accidental writes

## References

- PRD FR-1, FR-2, FR-8
- Constraints TC-1 through TC-4
