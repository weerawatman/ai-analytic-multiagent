# Technology Stack

**Phase:** 1  
**Last updated:** 2026-07-15

---

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Orchestration** | LangGraph | Already in codebase; supports HITL interrupts and multi-agent routing |
| **LLM Framework** | LangChain + Ollama | Local-only requirement; existing integration |
| **LLM Runtime** | Ollama (local) | No cloud API; ~14B default, ~32B optional on 32GB RAM |
| **Backend API** | FastAPI | Async, OpenAPI docs, existing codebase |
| **Frontend** | Streamlit | Existing UI; minimal changes for Phase 1 |
| **Business Data** | Microsoft Fabric DW | Single source of truth for SAP analytics (`WH_SAP_PRD`) |
| **Fabric Auth** | Entra ID Service Principal | App identity; not tied to personal credentials |
| **Fabric Driver** | pyodbc + ODBC Driver 18 for SQL Server | Standard Fabric/Synapse connectivity (TBD in build) |
| **App State — structured** | JSON files | Backlog + semantic — easy diff/review for Trusted promotion |
| **App State — chat** | SQLite | Conversation history; no Postgres overhead |
| **Validation** | Pydantic V2 | Request/response and backlog schemas |
| **Testing** | pytest | Existing test setup |
| **Runtime** | Native Windows (Python venv) | Simpler Fabric/Ollama debug vs Docker on Windows |
| **Containerization** | None (Phase 1) | Docker Compose retained in repo but not primary runtime |

---

## Default Models (Configurable)

| Setting | Default | Alternative |
|---------|---------|-------------|
| `OLLAMA_MODEL` | ~14B quant (e.g. `qwen2.5:14b` or `qwen2.5-coder:14b`) | ~32B quant when quality insufficient |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | — |

---

## Removed from Phase 1 Runtime Path

| Technology | Reason |
|------------|--------|
| PostgreSQL 16 | User decision — focus Fabric only; state via JSON/SQLite |
| Docker Compose (runtime) | Native preferred for Windows Fabric/Ollama integration |
| Cloud LLM APIs | Local-only constraint |

---

## Environment Variables (Phase 1)

```env
# Fabric
FABRIC_SERVER=
FABRIC_DATABASE=
FABRIC_TENANT_ID=
FABRIC_CLIENT_ID=
FABRIC_CLIENT_SECRET=

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b

# App
FASTAPI_HOST=127.0.0.1
FASTAPI_PORT=8000
STREAMLIT_PORT=8501
BACKEND_URL=http://127.0.0.1:8000
LOG_LEVEL=INFO

# Storage
DATA_LOCAL_DIR=data/local
DATA_TEMPLATES_DIR=data/templates
```

---

## References

- `knowledge/05-architecture/architecture/Architecture.md`
- `knowledge/03-prd/constraints.md`
