from fastapi import APIRouter, Query

from backend.app.schemas.phase2 import FeedbackCreate, FeedbackResponse
from backend.app.services.feedback_router import apply_feedback
from backend.app.services.feedback_store import add_feedback, load_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/{theme_id}", response_model=FeedbackResponse)
async def get_feedback(theme_id: str) -> FeedbackResponse:
    data = load_feedback(theme_id)
    return FeedbackResponse(theme_id=data["theme_id"], entries=data.get("entries", []))


@router.post("/{theme_id}", response_model=FeedbackResponse)
async def post_feedback(
    theme_id: str,
    body: FeedbackCreate,
    theme_name: str = Query(default=""),
) -> FeedbackResponse:
    data = add_feedback(
        theme_id,
        brief_id=body.brief_id,
        role=body.role,
        action=body.action,
        comment=body.comment,
    )
    routed = await apply_feedback(
        theme_id,
        role=body.role,
        action=body.action,
        comment=body.comment,
        brief_id=body.brief_id,
        theme_name=theme_name,
    )
    return FeedbackResponse(
        theme_id=data["theme_id"],
        entries=data.get("entries", []),
        routed=routed.get("applied", []),
    )
