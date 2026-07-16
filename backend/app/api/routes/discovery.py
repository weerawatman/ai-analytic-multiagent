import asyncio

from fastapi import APIRouter, HTTPException

from backend.app.schemas.phase2 import DiscoveryRunResponse
from backend.app.services.discovery_service import load_discovery, run_discovery

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/{theme_id}")
async def get_discovery(theme_id: str) -> dict:
    data = load_discovery(theme_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Discovery not found — run discovery first")
    return data


@router.post("/{theme_id}/run", response_model=DiscoveryRunResponse)
async def run_theme_discovery(theme_id: str) -> DiscoveryRunResponse:
    try:
        result = await asyncio.to_thread(run_discovery, theme_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return DiscoveryRunResponse(**result)
