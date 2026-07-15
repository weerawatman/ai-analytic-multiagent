from fastapi import APIRouter

from backend.app.services.semantic_store import read_draft_layer, read_trusted_layer

router = APIRouter(prefix="/semantic", tags=["semantic"])


@router.get("/trusted")
async def get_trusted_semantic() -> dict:
    return await read_trusted_layer()


@router.get("/draft")
async def get_draft_semantic() -> dict:
    return await read_draft_layer()
