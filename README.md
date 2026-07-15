# AI Analytics Multi-Agent System

Enterprise AI Data Team powered by **LangGraph**, **FastAPI**, **Streamlit**, and **Ollama** (qwen2.5-coder:7b).

## Architecture

```
User ──► Streamlit UI ──► FastAPI Backend ──► LangGraph Orchestrator
                                                  │
                              ┌────────────────────┼────────────────────┐
                              ▼                    ▼                    ▼
                        Data Engineer        Data Analyst        Data Scientist
                        (Schema &            (Text-to-SQL &      (ML Models &
                         Semantic Layer)       Pattern Analysis)   Forecasting)
                              │
                        [Human-in-the-Loop]
                        Approval Gate
```

### Agents

| Agent | Role |
|-------|------|
| **Data Engineer** | Extracts database schema, builds/updates semantic layer. Requests human approval for changes. |
| **Data Analyst** | Converts natural language to SQL, analyzes query results, identifies patterns. |
| **Data Scientist** | Proposes statistical models, ML approaches, and advanced analytics strategies. |

### Human-in-the-Loop

The Data Engineer agent can propose updates to the **semantic layer** (`data/semantic_layer.json`). When this happens, the LangGraph workflow **interrupts** and waits for user approval via the `/api/v1/approval/` endpoint before proceeding.

## Prerequisites

- **Docker & Docker Compose**
- **Ollama** running locally with `qwen2.5-coder:7b` model pulled:
  ```bash
  ollama pull qwen2.5-coder:7b
  ```

## Quick Start

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```

2. Start all services:
   ```bash
   docker compose up --build
   ```

3. Access the applications:

   | Service | URL |
   |---------|-----|
   | Streamlit UI | http://localhost:8501 |
   | FastAPI Docs | http://localhost:8000/docs |
   | Adminer (DB) | http://localhost:8080 |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat/` | Send a message to the AI Data Team |
| `POST` | `/api/v1/approval/` | Approve/reject semantic layer updates |
| `GET` | `/health` | Health check |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── api/routes/           # chat.py, approval.py
│   │   ├── core/                 # config.py, logger.py
│   │   ├── agents/               # LangGraph orchestrator + agents
│   │   ├── db/                   # Async SQLAlchemy + models
│   │   ├── schemas/              # Pydantic request/response models
│   │   └── services/             # semantic_store.py
│   ├── alembic/                  # Database migrations
│   └── tests/                    # Pytest
├── frontend/
│   ├── app.py                    # Streamlit main UI
│   └── components/               # UI components
├── data/
│   ├── init.sql                  # Dummy data (auto-loaded)
│   └── semantic_layer.json       # Semantic layer
└── docker-compose.yml
```

## Tech Stack

- **Backend**: FastAPI, LangGraph, LangChain, SQLAlchemy (async), Alembic, Pydantic V2
- **Frontend**: Streamlit
- **LLM**: Ollama (qwen2.5-coder:7b)
- **Database**: PostgreSQL 16
- **Containerization**: Docker & Docker Compose
