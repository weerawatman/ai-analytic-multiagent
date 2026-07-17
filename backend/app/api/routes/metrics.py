"""Metric Registry CRUD + preview (Phase G2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services import metric_registry
from backend.app.services.fabric_sql import get_active_sql_source, run_sql_async

router = APIRouter(prefix="/metrics", tags=["metrics"])


class MetricUpsert(BaseModel):
    metric_key: str
    name_th: str | None = None
    name_en: str | None = None
    status: str | None = None
    theme: str | None = None
    table: str | None = None
    time_column: str | None = None
    time_format: str | None = None
    expression: str | None = None
    aggregation: str | None = None
    dimensions: list[str] | None = None
    unit: str | None = None
    derived: dict[str, Any] | None = None
    baseline_question_tags: list[str] | None = None
    source: str | None = None
    owner_confirmed: bool | None = None
    change_reason: str | None = None


class MetricPreviewRequest(BaseModel):
    months: list[str] | None = None
    dimension: str | None = None
    limit: int = Field(default=12, ge=1, le=12)


@router.get("/")
async def list_metrics(
    theme: str | None = None,
    status: str | None = None,
    approved_only: bool = False,
) -> dict:
    items = await metric_registry.list_metrics(
        theme=theme, status=status, approved_only=approved_only
    )
    return {"items": items, "total": len(items)}


@router.get("/{metric_key:path}")
async def get_metric(metric_key: str) -> dict:
    item = await metric_registry.get_metric(metric_key)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Metric not found: {metric_key}")
    return item


@router.post("/", status_code=201)
async def upsert_metric(body: MetricUpsert) -> dict:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return await metric_registry.upsert_metric(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{metric_key:path}/approve")
async def approve_metric(metric_key: str) -> dict:
    try:
        return await metric_registry.approve_metric(metric_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{metric_key:path}/preview")
async def preview_metric(metric_key: str, body: MetricPreviewRequest | None = None) -> dict:
    body = body or MetricPreviewRequest()
    entry = await metric_registry.get_metric(metric_key)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Metric not found: {metric_key}")
    if entry.get("derived") or not entry.get("expression"):
        raise HTTPException(
            status_code=400,
            detail="Derived or expression-less metrics cannot be previewed via SQL",
        )
    source = get_active_sql_source()
    if source == "offline":
        raise HTTPException(status_code=503, detail="No SQL source available (offline)")
    try:
        sql = metric_registry.render_metric_sql(
            entry,
            source,
            months=body.months,
            dimension=body.dimension,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = await run_sql_async(sql, max_rows=body.limit, source=source)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Preview query failed: {type(exc).__name__}") from exc
    rows = (result.get("rows") or [])[: body.limit]
    return {
        "metric_key": metric_key,
        "sql": sql,
        "source": result.get("source", source),
        "rows": rows,
        "row_count": len(rows),
    }
