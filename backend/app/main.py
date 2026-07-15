from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import approval, chat
from backend.app.core.config import get_settings
from backend.app.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting AI Analytics Multi-Agent System")
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


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "ai-analytics-multiagent"}
