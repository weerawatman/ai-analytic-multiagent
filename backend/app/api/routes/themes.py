from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.themes import ThemeScanResponse
from backend.app.services.fabric_connector import FabricConnectionError
from backend.app.services.theme_service import get_themes, scan_themes

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("/", response_model=ThemeScanResponse)
async def list_themes() -> ThemeScanResponse:
    data = get_themes()
    return ThemeScanResponse(**data)


@router.post("/scan", response_model=ThemeScanResponse)
async def scan_schema_themes(
    use_llm: bool = Query(default=True, description="Use Ollama to refine theme labels"),
) -> ThemeScanResponse:
    try:
        data = await scan_themes(use_llm=use_llm)
        return ThemeScanResponse(**data)
    except FabricConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail={"detail": str(exc), "detail_th": exc.message_th},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
