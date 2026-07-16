from fastapi import APIRouter, HTTPException

from backend.app.schemas.phase2 import OnboardingResponse, TeamMemoryResponse
from backend.app.services.onboarding_service import run_onboarding
from backend.app.services.team_memory_store import load_team_memory

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/{theme_id}", response_model=TeamMemoryResponse)
async def get_team_memory(theme_id: str) -> TeamMemoryResponse:
    data = load_team_memory(theme_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Team memory not found — run onboarding first")
    return TeamMemoryResponse(**data)


@router.post("/{theme_id}/run", response_model=OnboardingResponse)
async def run_theme_onboarding(theme_id: str, theme_name: str = "") -> OnboardingResponse:
    try:
        result = await run_onboarding(theme_id, theme_name=theme_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return OnboardingResponse(**result)
