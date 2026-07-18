"""Analytics snapshot status / series / refresh (Phase H)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services import job_runner, snapshot_refresh_service, snapshot_store
from backend.app.services.job_runner import JobConflictError

router = APIRouter(prefix="/analytics", tags=["analytics"])


class RefreshRequest(BaseModel):
    mode: Literal["auto", "backfill", "incremental"] = "auto"
    end_month: str | None = Field(
        default=None, description="YYYYMM end of window; default = current UTC month"
    )
    metric_keys: list[str] | None = None


@router.get("/status")
async def analytics_status() -> dict[str, Any]:
    snapshot_store.init_analytics_db()
    return snapshot_store.snapshot_status()


@router.get("/runs")
async def list_snapshot_runs(limit: int = 20) -> dict[str, Any]:
    snapshot_store.init_analytics_db()
    runs = snapshot_store.list_runs(limit=min(max(limit, 1), 100))
    return {"items": runs, "total": len(runs)}


@router.get("/series/{metric_key:path}")
async def get_metric_series(
    metric_key: str,
    dim_name: str = "__total__",
    dim_value: str = "__total__",
) -> dict[str, Any]:
    snapshot_store.init_analytics_db()
    series = snapshot_store.get_series(
        metric_key, dim_name=dim_name, dim_value=dim_value
    )
    return {
        "metric_key": metric_key,
        "dim_name": dim_name,
        "dim_value": dim_value,
        "points": series,
        "n": len(series),
    }


@router.get("/detectors/summary")
async def detectors_summary(theme: str | None = None) -> dict[str, Any]:
    snapshot_store.init_analytics_db()
    text = snapshot_refresh_service.summarize_detectors_for_theme(theme)
    return {"theme": theme, "analytics_context": text, "empty": not bool(text)}


@router.post("/refresh", status_code=202)
async def refresh_snapshots(body: RefreshRequest | None = None) -> dict[str, Any]:
    body = body or RefreshRequest()
    try:
        job = job_runner.start_snapshot_refresh_job(
            mode=body.mode,
            end_month=body.end_month,
            metric_keys=body.metric_keys,
        )
    except JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A snapshot_refresh job is already active",
                "job_id": exc.job.get("id"),
                "status": exc.job.get("status"),
            },
        ) from exc
    return {
        "job_id": job["id"],
        "kind": job["kind"],
        "status": job["status"],
        "mode": body.mode,
    }
