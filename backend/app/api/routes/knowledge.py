from fastapi import APIRouter, HTTPException

from backend.app.schemas.phase2 import (
    KnowledgeItemCreate,
    KnowledgeItemResponse,
    SapTableImportRequest,
    SapTableImportResponse,
    SapTableLookupResponse,
    SapTableStatsResponse,
)
from backend.app.services import knowledge_store
from backend.app.services.sap_table_store import (
    get_stats,
    import_from_csv,
    lookup_for_table_ref,
    tabname_candidates,
)

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


@router.get("/sap-tables/stats", response_model=SapTableStatsResponse)
async def sap_tables_stats() -> SapTableStatsResponse:
    return SapTableStatsResponse(**get_stats())


@router.post("/sap-tables/import", response_model=SapTableImportResponse)
async def sap_tables_import(body: SapTableImportRequest) -> SapTableImportResponse:
    try:
        result = import_from_csv(
            body.csv_path,
            language=body.language,
            replace=body.replace,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc
    return SapTableImportResponse(**result)


@router.get("/sap-tables/lookup/{table_ref:path}", response_model=SapTableLookupResponse)
async def sap_tables_lookup(table_ref: str, language: str = "E") -> SapTableLookupResponse:
    match = lookup_for_table_ref(table_ref, language=language)
    if not match:
        return SapTableLookupResponse(
            fabric_ref=table_ref,
            matched=False,
            sap_tabname=tabname_candidates(table_ref)[0] if tabname_candidates(table_ref) else None,
        )
    return SapTableLookupResponse(
        fabric_ref=match["fabric_ref"],
        sap_tabname=match["sap_tabname"],
        description=match["description"],
        matched=True,
    )
