from fastapi import APIRouter, HTTPException

from backend.app.schemas.phase2 import BriefingResponse
from backend.app.services.briefing_service import generate_briefings, load_briefings

router = APIRouter(prefix="/briefings", tags=["briefings"])


@router.get("/{theme_id}", response_model=BriefingResponse)
async def get_briefings(theme_id: str) -> BriefingResponse:
    data = load_briefings(theme_id)
    if data is None:
        raise HTTPException(status_code=404, detail="No briefings — generate after discovery")
    return BriefingResponse(**data)


@router.post("/{theme_id}/generate", response_model=BriefingResponse)
async def generate_theme_briefings(theme_id: str, theme_name: str = "") -> BriefingResponse:
    try:
        result = await generate_briefings(theme_id, theme_name=theme_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BriefingResponse(**result)
