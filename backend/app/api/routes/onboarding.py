from fastapi import APIRouter, HTTPException

from backend.app.schemas.jobs import JobSubmitResponse
from backend.app.schemas.phase2 import TeamMemoryResponse
from backend.app.services import job_runner
from backend.app.services.deep_profile_service import load_homework
from backend.app.services.discovery_service import load_discovery
from backend.app.services.insight_starter_service import load_starter_pack
from backend.app.services.team_memory_store import load_team_memory

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/{theme_id}", response_model=TeamMemoryResponse)
async def get_team_memory(theme_id: str) -> TeamMemoryResponse:
    data = load_team_memory(theme_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Team memory not found — run onboarding first")
    return TeamMemoryResponse(**data)


@router.get("/{theme_id}/homework")
async def get_homework(theme_id: str) -> dict:
    data = load_homework(theme_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Homework not found — run deep onboarding first",
        )
    return data


@router.get("/{theme_id}/starter-pack")
async def get_starter_pack(theme_id: str) -> dict:
    data = load_starter_pack(theme_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Starter pack not found — run deep onboarding first",
        )
    return data


@router.post("/{theme_id}/deep-run", response_model=JobSubmitResponse, status_code=202)
async def run_deep_onboarding(theme_id: str, theme_name: str = "") -> JobSubmitResponse:
    """Submit deterministic deep profiling (homework + starter pack) — no LLM."""
    if not load_discovery(theme_id):
        raise HTTPException(
            status_code=400,
            detail=f"No discovery for theme {theme_id} — run discovery first",
        )
    try:
        job = job_runner.start_deep_onboarding_job(theme_id, theme_name)
    except job_runner.JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Deep onboarding is already running for this theme",
                "job_id": exc.job["id"],
            },
        ) from exc

    return JobSubmitResponse(
        job_id=job["id"],
        thread_id=theme_id,
        status=job["status"],
        kind="deep_onboarding",
    )


@router.post("/{theme_id}/run", response_model=JobSubmitResponse, status_code=202)
async def run_theme_onboarding(theme_id: str, theme_name: str = "") -> JobSubmitResponse:
    """Submit a team onboarding run — returns a job to poll at /api/v1/jobs/{job_id}."""
    if not load_discovery(theme_id):
        raise HTTPException(
            status_code=400,
            detail=f"No discovery for theme {theme_id} — run discovery first",
        )
    try:
        job = job_runner.start_onboarding_job(theme_id, theme_name)
    except job_runner.JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Onboarding is already running for this theme",
                "job_id": exc.job["id"],
            },
        ) from exc

    return JobSubmitResponse(
        job_id=job["id"],
        thread_id=theme_id,
        status=job["status"],
        kind="onboarding",
    )
