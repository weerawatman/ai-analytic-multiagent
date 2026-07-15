from fastapi import APIRouter

from backend.app.schemas.validation import Phase1ValidationResponse
from backend.app.services.phase1_validator import run_phase1_validation

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/phase1", response_model=Phase1ValidationResponse)
async def validate_phase1() -> Phase1ValidationResponse:
    """Run Phase 1 Definition of Done checks against local state."""
    result = await run_phase1_validation()
    return Phase1ValidationResponse(**result)
