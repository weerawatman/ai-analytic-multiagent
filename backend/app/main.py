from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import (
    approval,
    backlog,
    briefings,
    chat,
    discovery,
    fabric,
    feedback,
    knowledge,
    semantic,
    sessions,
    themes,
    validation,
)
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.chat_store import init_chat_db
from backend.app.services.local_paths import ensure_local_structure


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting AI Analytics Multi-Agent System")
    ensure_local_structure()
    init_chat_db()
    logger.info("Local storage initialized (SQLite + JSON)")
    yield
    logger.info("Shutting down AI Analytics Multi-Agent System")


settings = get_settings()

app = FastAPI(
    title="AI Analytics Multi-Agent API",
    description="Enterprise AI Data Team powered by LangGraph + Ollama",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s | path=%s", exc, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."},
    )


# Routes
app.include_router(chat.router, prefix="/api/v1")
app.include_router(approval.router, prefix="/api/v1")
app.include_router(fabric.router, prefix="/api/v1")
app.include_router(backlog.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(semantic.router, prefix="/api/v1")
app.include_router(themes.router, prefix="/api/v1")
app.include_router(validation.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(briefings.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, object]:
    from backend.app.services.fabric_connector import get_fabric_connector

    connector = get_fabric_connector()
    fabric_status: dict[str, object] = {
        "configured": connector.is_configured(),
        "connected": False,
    }
    if connector.is_configured():
        try:
            fabric_status = {**fabric_status, **connector.ping(), "connected": True}
        except Exception as exc:
            fabric_status["error"] = str(exc)

    return {
        "status": "healthy",
        "service": "ai-analytics-multiagent",
        "fabric": fabric_status,
    }
