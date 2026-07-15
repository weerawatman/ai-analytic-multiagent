from fastapi import APIRouter, HTTPException

from backend.app.schemas.semantic import (
    PromotionApproveRequest,
    PromotionApproveResponse,
    PromotionPreviewResponse,
    TrustedMetricPreview,
)
from backend.app.services.promotion_service import approve_promotion, get_promotion_preview
from backend.app.services.semantic_store import read_draft_layer, read_trusted_layer

router = APIRouter(prefix="/semantic", tags=["semantic"])


@router.get("/trusted")
async def get_trusted_semantic() -> dict:
    return await read_trusted_layer()


@router.get("/draft")
async def get_draft_semantic() -> dict:
    return await read_draft_layer()


@router.get("/promote/{item_id}/preview", response_model=PromotionPreviewResponse)
async def preview_promotion(item_id: str) -> PromotionPreviewResponse:
    try:
        preview = get_promotion_preview(item_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromotionPreviewResponse(**preview)


@router.post("/promote/{item_id}/approve", response_model=PromotionApproveResponse)
async def approve_promotion_endpoint(
    item_id: str,
    request: PromotionApproveRequest,
) -> PromotionApproveResponse:
    try:
        result = await approve_promotion(
            item_id,
            approved=request.approved,
            overrides=request.model_dump(exclude={"approved", "approved_by"}, exclude_unset=True),
            approved_by=request.approved_by,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    metric = result.get("metric")
    return PromotionApproveResponse(
        item_id=result["item_id"],
        status=result["status"],
        metric=TrustedMetricPreview(**metric) if metric else None,
    )
