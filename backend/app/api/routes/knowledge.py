from fastapi import APIRouter, HTTPException

from backend.app.schemas.phase2 import KnowledgeItemCreate, KnowledgeItemResponse
from backend.app.services import knowledge_store

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/glossary")
async def list_glossary(theme: str | None = None) -> list[dict]:
    return await knowledge_store.list_items("glossary", theme=theme)


@router.post("/glossary", response_model=KnowledgeItemResponse, status_code=201)
async def create_glossary(item: KnowledgeItemCreate) -> KnowledgeItemResponse:
    created = await knowledge_store.add_item("glossary", item.model_dump(exclude_unset=True))
    return KnowledgeItemResponse(
        id=created["id"],
        status=created.get("status", "draft"),
        created_at=created["created_at"],
        updated_at=created["updated_at"],
    )


@router.get("/targets")
async def list_targets(theme: str | None = None) -> list[dict]:
    return await knowledge_store.list_items("targets", theme=theme)


@router.post("/targets", response_model=KnowledgeItemResponse, status_code=201)
async def create_target(item: KnowledgeItemCreate) -> KnowledgeItemResponse:
    created = await knowledge_store.add_item("targets", item.model_dump(exclude_unset=True))
    return KnowledgeItemResponse(
        id=created["id"],
        status=created.get("status", "draft"),
        created_at=created["created_at"],
        updated_at=created["updated_at"],
    )


@router.get("/relationships")
async def list_relationships(theme: str | None = None) -> list[dict]:
    return await knowledge_store.list_items("relationships", theme=theme)


@router.post("/relationships", response_model=KnowledgeItemResponse, status_code=201)
async def create_relationship(item: KnowledgeItemCreate) -> KnowledgeItemResponse:
    created = await knowledge_store.add_item("relationships", item.model_dump(exclude_unset=True))
    return KnowledgeItemResponse(
        id=created["id"],
        status=created.get("status", "draft"),
        created_at=created["created_at"],
        updated_at=created["updated_at"],
    )


@router.patch("/{kind}/{item_id}/approve")
async def approve_knowledge_item(kind: str, item_id: str) -> dict:
    if kind not in ("glossary", "targets", "relationships"):
        raise HTTPException(status_code=400, detail="Invalid knowledge kind")
    try:
        return await knowledge_store.update_item(kind, item_id, {"status": "approved"})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
