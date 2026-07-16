import asyncio

from fastapi import APIRouter, HTTPException

from backend.app.core.logger import logger
from backend.app.services.fabric_connector import FabricConnectionError, get_fabric_connector
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql

router = APIRouter(prefix="/fabric", tags=["fabric"])


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
