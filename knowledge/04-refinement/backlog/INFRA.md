# INFRA-1: Fabric Service Principal Connector

**Epic:** M1 Foundation  
**Priority:** Must  
**Estimate:** M  
**AC:** AC-1

## User Story
As a Data Engineer, I want the backend to connect to Fabric DW using Service Principal so that agents can query real SAP data.

## Tasks
- [ ] Add Fabric env vars to `Settings` and `.env.example`
- [ ] Implement `FabricConnector` with pyodbc + Entra SP auth
- [ ] Connection pool / single connection with retry
- [ ] Unit test with mock connection

## Acceptance
- Given valid `.env`, When health check runs, Then `connected: true` for `WH_SAP_PRD`

---

# INFRA-2: SQL Read-Only Guard

**Epic:** M1 Foundation  
**Priority:** Must  
**Estimate:** S  
**AC:** AC-1

## User Story
As a Data Engineer, I want all agent SQL validated before execution so that Fabric DW is never modified.

## Tasks
- [ ] Implement SQL parser/allowlist (SELECT/WITH only)
- [ ] Blocklist DDL/DML/EXEC keywords
- [ ] Return structured error to agent on rejection
- [ ] Log all executed SQL with mode tag

## Acceptance
- Given `DELETE FROM x`, When guard validates, Then query blocked with Thai error message

---

# INFRA-3: Fabric Health Endpoint

**Epic:** M1 Foundation  
**Priority:** Must  
**Estimate:** S  
**AC:** AC-1

## User Story
As a Data Engineer, I want to see Fabric connection status so that I know the system is ready.

## Tasks
- [ ] `GET /api/v1/fabric/health` endpoint
- [ ] Extend `GET /health` with fabric sub-status
- [ ] Streamlit status indicator (sidebar)

## Acceptance
- Given Fabric up, When GET health, Then returns connected + database name

---

# INFRA-4: Native Runtime Config

**Epic:** M1 Foundation  
**Priority:** Must  
**Estimate:** S  
**AC:** AC-9

## User Story
As a Data Engineer, I want to run FastAPI + Streamlit natively on Windows without Docker.

## Tasks
- [ ] Update config defaults: `localhost`, Ollama `127.0.0.1:11434`
- [ ] Add `scripts/run-backend.ps1` and `scripts/run-frontend.ps1`
- [ ] Document native setup in README section

## Acceptance
- Given no Docker running, When scripts executed, Then app starts and connects to Ollama
