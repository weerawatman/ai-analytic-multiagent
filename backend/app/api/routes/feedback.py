from fastapi import APIRouter

from backend.app.schemas.phase2 import FeedbackCreate, FeedbackResponse
from backend.app.services.feedback_store import add_feedback, load_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/{theme_id}", response_model=FeedbackResponse)
async def get_feedback(theme_id: str) -> FeedbackResponse:
    data = load_feedback(theme_id)
    return FeedbackResponse(theme_id=data["theme_id"], entries=data.get("entries", []))


@router.post("/{theme_id}", response_model=FeedbackResponse)
async def post_feedback(theme_id: str, body: FeedbackCreate) -> FeedbackResponse:
    data = add_feedback(
        theme_id,
        brief_id=body.brief_id,
        role=body.role,
        action=body.action,
        comment=body.comment,
    )
    return FeedbackResponse(theme_id=data["theme_id"], entries=data.get("entries", []))
