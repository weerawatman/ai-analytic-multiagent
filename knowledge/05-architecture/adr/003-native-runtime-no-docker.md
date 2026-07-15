# ADR-003: Native Windows Runtime (No Docker Phase 1)

## Status: Accepted

## Context

The existing project uses Docker Compose with PostgreSQL, backend, frontend, and Adminer. The owner runs on Windows 11 (32GB RAM, Ryzen AI) with local Ollama and Fabric connectivity. Docker on Windows adds friction for Service Principal auth and Ollama networking.

## Decision

- Run **FastAPI + Streamlit + Ollama natively** on Windows for Phase 1
- Keep Docker files in repo for future use but do not require Docker for daily development
- Bind services to **localhost** only

## Consequences

**Easier:**
- Direct Fabric ODBC connectivity debugging
- Ollama at `localhost:11434` without `host.docker.internal`
- Faster iteration for solo developer

**Harder:**
- Manual Python venv setup per machine
- Environment differences not containerized
- Phase 2 team onboarding may need Docker revisit

## References

- Constraints TC-5
- Tech stack: Runtime row
