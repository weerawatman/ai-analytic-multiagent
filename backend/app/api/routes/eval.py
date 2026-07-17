"""Eval API — list golden questions / trigger harness baseline (Phase G3)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services import eval_service

router = APIRouter(prefix="/eval", tags=["eval"])


class EvalRunRequest(BaseModel):
    harness_baseline: bool = Field(
        default=True,
        description="If true, skip chat pipeline and record empty-answer baseline",
    )


@router.get("/golden-questions")
async def list_golden_questions(active_only: bool = True) -> dict:
    items = eval_service.load_golden_questions(active_only=active_only)
    return {"items": items, "total": len(items)}


@router.post("/run")
async def run_eval(body: EvalRunRequest | None = None) -> dict:
    body = body or EvalRunRequest()
    try:
        return await eval_service.run_eval(harness_baseline=body.harness_baseline)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eval failed: {type(exc).__name__}") from exc
