"""Job status/polling endpoints for long-running chat and onboarding runs."""

from fastapi import APIRouter, HTTPException

from backend.app.schemas.jobs import JobStatusResponse
from backend.app.services import job_runner, job_store

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/", response_model=list[JobStatusResponse])
async def list_jobs(
    thread_id: str | None = None,
    kind: str | None = None,
    active: bool = False,
    limit: int = 20,
) -> list[JobStatusResponse]:
    jobs = job_store.list_jobs(thread_id=thread_id, kind=kind, active_only=active, limit=limit)
    return [JobStatusResponse(**job) for job in jobs]


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@router.post("/{job_id}/cancel", response_model=JobStatusResponse)
async def cancel_job(job_id: str) -> JobStatusResponse:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in job_store.ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Job already {job['status']}")
    job_runner.cancel_job(job_id)
    refreshed = job_store.get_job(job_id)
    return JobStatusResponse(**(refreshed or job))
