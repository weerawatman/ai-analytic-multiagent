"""Proactive insight feed endpoints (Phase I)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services import insight_store, job_runner
from backend.app.services.job_runner import JobConflictError

router = APIRouter(prefix="/insights", tags=["insights"])


class RefreshRequest(BaseModel):
    theme_id: str | None = None
    top_k: int | None = None


class FeedbackRequest(BaseModel):
    label: str = Field(..., description="'useful' | 'not_useful' | 'wrong'")
    comment: str | None = None
    user_id: str | None = None


@router.get("/status")
async def insights_status() -> dict[str, Any]:
    insight_store.init_insight_tables()
    return {
        "status_counts": insight_store.insight_status_summary(),
        "feedback": insight_store.feedback_stats(),
    }


@router.get("/")
async def list_insights(
    status: str = "published",
    theme_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    insight_store.init_insight_tables()
    items = insight_store.list_insights(
        status=status, theme_id=theme_id, limit=min(max(limit, 1), 200)
    )
    return {"items": items, "total": len(items)}


@router.get("/{insight_id}")
async def get_insight(insight_id: str) -> dict[str, Any]:
    insight_store.init_insight_tables()
    insight = insight_store.get_insight(insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight["feedback"] = insight_store.list_feedback(insight_id)
    return insight


@router.post("/{insight_id}/feedback", status_code=201)
async def add_feedback(insight_id: str, body: FeedbackRequest) -> dict[str, Any]:
    insight_store.init_insight_tables()
    if insight_store.get_insight(insight_id) is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    try:
        return insight_store.add_feedback(
            insight_id, label=body.label, comment=body.comment, user_id=body.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh", status_code=202)
async def refresh_insights(body: RefreshRequest | None = None) -> dict[str, Any]:
    body = body or RefreshRequest()
    try:
        job = job_runner.start_insight_pipeline_job(theme_id=body.theme_id, top_k=body.top_k)
    except JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "An insight_pipeline job is already active",
                "job_id": exc.job.get("id"),
                "status": exc.job.get("status"),
            },
        ) from exc
    return {"job_id": job["id"], "kind": job["kind"], "status": job["status"]}
