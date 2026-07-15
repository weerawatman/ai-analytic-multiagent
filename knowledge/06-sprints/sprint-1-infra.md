# Build Sprint 1 — Foundation & Fabric Connect

**Stage:** 06 Build  
**Date:** 2026-07-15  
**Stories:** INFRA-1, INFRA-2, INFRA-3, INFRA-4  
**Status:** Complete — pending commit sign-off

---

## Delivered

| Story | Implementation |
|-------|----------------|
| INFRA-1 | `backend/app/services/fabric_connector.py` — SP auth via azure-identity + pyodbc |
| INFRA-2 | `backend/app/services/sql_guard.py` — SELECT/WITH only, blocklist |
| INFRA-3 | `GET /api/v1/fabric/health`, extended `GET /health` |
| INFRA-4 | Native defaults in config, `scripts/run-backend.ps1`, `scripts/run-frontend.ps1` |

## Config / Deps

- Updated `backend/app/core/config.py` — Fabric env vars, localhost defaults
- Updated `.env.example`
- Added `pyodbc`, `azure-identity` to requirements

## Tests

- `backend/tests/test_sql_guard.py` — guard unit tests
- Updated `test_health.py` — fabric sub-status

## AC Coverage

- AC-1: Ready (requires live Fabric `.env` for integration test)
- SQL guard blocks DELETE/INSERT (unit tested)

## Manual Verification

```powershell
# 1. Copy .env.example → .env and fill Fabric SP credentials
# 2. Install ODBC Driver 18 for SQL Server
.\scripts\run-backend.ps1
# 3. GET http://127.0.0.1:8000/api/v1/fabric/health
```

## Next Sprint

Build Sprint 2 — STORE-1, STORE-2, STORE-3 (SQLite + JSON storage)
