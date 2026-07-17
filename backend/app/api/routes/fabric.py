import asyncio

from fastapi import APIRouter, HTTPException

from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.fabric_connector import FabricConnectionError, get_fabric_connector
from backend.app.services.fabric_sql import (
    fabric_can_query,
    pg_can_query,
)
from backend.app.services.postgres_replica import get_postgres_connector
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql

router = APIRouter(prefix="/fabric", tags=["fabric"])

# Thai messaging per active source — the UI shows these verbatim so the CEO
# always knows where an answer's data will come from (provenance, Phase F).
SOURCE_DETAIL_TH = {
    "fabric": "เชื่อมต่อ Fabric DW แล้ว — ใช้แหล่งข้อมูลหลักตามปกติ",
    "postgres": (
        "Fabric ไม่พร้อม (pause/unreachable) — สลับใช้ฐานข้อมูลสำรอง Postgres mirror อัตโนมัติ "
        "(ข้อมูลชุดเดียวกัน แต่ sync ล่าสุดอาจช้ากว่า Fabric)"
    ),
    "offline": (
        "ทั้ง Fabric และ Postgres mirror ไม่พร้อม — โหมด Offline: ใช้ discovery บนดิสก์ + draft SQL "
        "(ไม่รัน SQL จริง)"
    ),
}


@router.get("/health")
async def fabric_health() -> dict:
    """Check Fabric DW connectivity."""
    connector = get_fabric_connector()
    if not connector.is_configured():
        return {
            "connected": False,
            "configured": False,
            "detail": "Fabric credentials not configured",
            "detail_th": "ยังไม่ได้ตั้งค่า Fabric ใน .env",
        }

    try:
        result = await asyncio.to_thread(connector.ping)
        return {
            "connected": True,
            "configured": True,
            **result,
        }
    except FabricConnectionError as exc:
        logger.error("Fabric health check failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "connected": False,
                "configured": True,
                "detail": str(exc),
                "detail_th": exc.message_th,
            },
        ) from exc
    except Exception as exc:
        logger.error("Fabric health check unexpected error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "connected": False,
                "configured": True,
                "detail": str(exc),
                "detail_th": "เชื่อมต่อ Fabric ไม่สำเร็จ กรุณาตรวจสอบ SP และ ODBC Driver",
            },
        ) from exc


@router.get("/sources")
async def data_sources_status() -> dict:
    """Active SQL source + per-source status (Fabric primary, Postgres fallback).

    Reachability uses the same TTL-cached pings the dispatch path uses, so this
    endpoint reflects what the next query would actually do. No secrets are
    returned — database names only.
    """
    settings = get_settings()
    fabric_connector = get_fabric_connector()
    pg_connector = get_postgres_connector()

    # Blocking pings (pyodbc/psycopg2) stay off the event loop.
    fabric_ok = await asyncio.to_thread(fabric_can_query)
    pg_ok = await asyncio.to_thread(pg_can_query)

    active = "fabric" if fabric_ok else ("postgres" if pg_ok else "offline")
    return {
        "active_source": active,
        "detail_th": SOURCE_DETAIL_TH[active],
        "fabric": {
            "configured": fabric_connector.is_configured(),
            "sql_enabled": settings.fabric_sql_enabled,
            "reachable": fabric_ok,
            "database": settings.fabric_database or None,
        },
        "postgres_replica": {
            "configured": pg_connector.is_configured(),
            "reachable": pg_ok,
            "database": settings.pg_replica_db or None,
        },
    }


@router.post("/validate-sql")
async def validate_sql(payload: dict) -> dict:
    """Validate SQL without executing (for testing guard)."""
    sql = payload.get("sql", "")
    try:
        safe = validate_read_only_sql(sql)
        return {"valid": True, "sql": safe}
    except SQLGuardError as exc:
        return {
            "valid": False,
            "detail": str(exc),
            "detail_th": exc.message_th,
        }
