from fastapi import APIRouter, HTTPException

from backend.app.core.logger import logger
from backend.app.schemas.backlog import BacklogItemResponse
from backend.app.schemas.chat import ChatRequest
from backend.app.schemas.jobs import JobSubmitResponse
from backend.app.services import job_runner
from backend.app.services.quality_assembly import save_quality_to_backlog

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=JobSubmitResponse, status_code=202)
async def chat(request: ChatRequest) -> JobSubmitResponse:
    """Submit a question to the AI Data Team — returns a job to poll at /api/v1/jobs/{job_id}."""
    logger.info(
        "Chat submit: thread=%s mode=%s message=%s...",
        request.thread_id,
        request.mode,
        request.message[:80],
    )
    try:
        job = job_runner.start_chat_job(request)
    except job_runner.JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Thread is still processing a previous question — wait for it to finish",
                "job_id": exc.job["id"],
            },
        ) from exc

    return JobSubmitResponse(
        job_id=job["id"],
        thread_id=request.thread_id,
        status=job["status"],
        kind="chat",
    )


@router.post("/save-candidate", response_model=BacklogItemResponse)
async def save_candidate(payload: dict) -> BacklogItemResponse:
    """Save quality payload to insight backlog (Quality Bar D)."""
    try:
        item = save_quality_to_backlog(payload)
        return BacklogItemResponse(**item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
