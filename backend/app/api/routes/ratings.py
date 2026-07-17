"""Answer rating endpoints (Phase G1b) — 👍/👎 feedback on chat answers."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from backend.app.services import chat_store

router = APIRouter(prefix="/chat", tags=["ratings"])


class RatingCreate(BaseModel):
    session_id: str
    rating: str = Field(..., description="'up' | 'down'")
    message_id: int | None = None
    job_id: str | None = None
    reason_tag: str | None = Field(
        None, description="'wrong_number'|'wrong_metric'|'too_slow'|'unclear'"
    )
    comment: str | None = None
    corrected_answer: str | None = None


@router.post("/rating", status_code=201)
async def create_rating(body: RatingCreate) -> dict:
    try:
        return chat_store.add_answer_rating(
            body.session_id,
            rating=body.rating,
            message_id=body.message_id,
            job_id=body.job_id,
            reason_tag=body.reason_tag,
            comment=body.comment,
            corrected_answer=body.corrected_answer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ratings")
async def get_ratings(session_id: str | None = None, limit: int = 50) -> dict:
    items = chat_store.list_answer_ratings(session_id=session_id, limit=limit)
    return {
        "items": items,
        "total": chat_store.count_answer_ratings(),
    }
