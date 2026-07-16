"""Claude external consultant API — status + on-demand consult jobs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.schemas.jobs import JobSubmitResponse
from backend.app.services import consultant_service, job_runner

router = APIRouter(prefix="/consultant", tags=["Consultant"])


class ConsultRequest(BaseModel):
    question: str = Field(..., min_length=1)


@router.get("/status")
async def consultant_status() -> dict:
    settings = get_settings()
    return {
        "enabled": settings.consultant_is_enabled,
        "model": settings.consultant_model,
        "modes": {
            "review_chat": settings.consultant_review_chat,
            "coach_onboarding": settings.consultant_coach_onboarding,
            "on_demand": settings.consultant_on_demand,
            "help_when_stuck": settings.consultant_help_when_stuck,
        },
    }


@router.post("/{theme_id}/consult", response_model=JobSubmitResponse, status_code=202)
async def consult(theme_id: str, body: ConsultRequest) -> JobSubmitResponse:
    if not consultant_service.is_enabled("on_demand"):
        raise HTTPException(
            status_code=503,
            detail="Consultant on-demand mode is disabled — set CONSULTANT_ENABLED + ANTHROPIC_API_KEY",
        )
    try:
        job = job_runner.start_consult_job(theme_id, body.question)
    except job_runner.JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A consult job is already running for this theme",
                "job_id": exc.job["id"],
            },
        ) from exc

    return JobSubmitResponse(
        job_id=job["id"],
        thread_id=theme_id,
        status=job["status"],
        kind="consult",
    )
