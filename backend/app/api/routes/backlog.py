from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.backlog import (
    BacklogCreateRequest,
    BacklogExportResponse,
    BacklogItemResponse,
    BacklogUpdateRequest,
)
from backend.app.services import backlog_store
from backend.app.services.report_generator import export_backlog_item

router = APIRouter(prefix="/backlog", tags=["backlog"])


@router.get("/", response_model=list[BacklogItemResponse])
async def list_backlog(
    status: str | None = Query(default=None),
    theme: str | None = Query(default=None),
) -> list[BacklogItemResponse]:
    items = backlog_store.list_items(status=status, theme=theme)
    return [BacklogItemResponse(**item) for item in items]


@router.get("/{item_id}", response_model=BacklogItemResponse)
async def get_backlog_item(item_id: str) -> BacklogItemResponse:
    item = backlog_store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    return BacklogItemResponse(**item)


@router.post("/", response_model=BacklogItemResponse, status_code=201)
async def create_backlog_item(request: BacklogCreateRequest) -> BacklogItemResponse:
    item = backlog_store.create_item(request.model_dump())
    return BacklogItemResponse(**item)


@router.patch("/{item_id}", response_model=BacklogItemResponse)
async def update_backlog_item(
    item_id: str,
    request: BacklogUpdateRequest,
) -> BacklogItemResponse:
    updates = request.model_dump(exclude_unset=True)
    try:
        item = backlog_store.update_item(item_id, updates)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BacklogItemResponse(**item)


@router.post("/{item_id}/export", response_model=BacklogExportResponse)
async def export_backlog_report(item_id: str) -> BacklogExportResponse:
    item = backlog_store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    result = export_backlog_item(item)
    return BacklogExportResponse(**result)
