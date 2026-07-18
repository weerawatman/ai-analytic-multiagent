"""Board digests + curriculum study API (Phase K)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services import curriculum_store, digest_service, job_runner
from backend.app.services.job_runner import JobConflictError

router = APIRouter(tags=["phase-k"])


class DigestGenerateRequest(BaseModel):
    week_key: str | None = None
    polish: bool | None = None


class StudyStartRequest(BaseModel):
    theme_id: str = "sales"
    theme_name: str = ""
    roles: list[str] | None = None


class StudyApproveRequest(BaseModel):
    theme_id: str
    result_id: str
    approved: bool = True


@router.get("/digests")
async def list_digests(limit: int = 12) -> dict:
    items = digest_service.list_digests(limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/digests/current")
async def get_current_digest() -> dict:
    data = digest_service.load_digest()
    if data is None:
        raise HTTPException(status_code=404, detail="No digest for current ISO week yet")
    return data


@router.get("/digests/{week_key}")
async def get_digest(week_key: str) -> dict:
    data = digest_service.load_digest(week_key)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No digest for {week_key}")
    return data


@router.post("/digests/generate")
async def generate_digest(body: DigestGenerateRequest | None = None) -> dict:
    body = body or DigestGenerateRequest()
    return await digest_service.generate_digest(
        week_key=body.week_key, polish=body.polish
    )


@router.get("/curriculum")
async def curriculum_summary() -> dict:
    curriculum_store.ensure_all_curricula()
    return curriculum_store.pass_rate_summary()


@router.get("/curriculum/{role}")
async def get_curriculum(role: str) -> dict:
    try:
        return curriculum_store.load_curriculum(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/curriculum/seed")
async def seed_curricula(force: bool = False) -> dict:
    return curriculum_store.ensure_all_curricula(force=force)


@router.post("/study/run")
async def start_study(body: StudyStartRequest | None = None) -> dict:
    body = body or StudyStartRequest()
    try:
        job = job_runner.start_study_job(
            theme_id=body.theme_id,
            theme_name=body.theme_name,
            roles=body.roles,
        )
    except JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A study job is already active",
                "job_id": exc.job.get("id"),
            },
        ) from exc
    return {"job_id": job["id"], "status": job.get("status")}


@router.post("/study/approve")
async def approve_study(body: StudyApproveRequest) -> dict:
    try:
        return curriculum_store.approve_study_result(
            body.theme_id, body.result_id, approved=body.approved
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
