"""Helpers for Fabric SQL execution and schema preview."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.app.services.fabric_connector import FabricConnectionError, get_fabric_connector


def fabric_is_available() -> bool:
    return get_fabric_connector().is_configured()


def run_fabric_sql(sql: str, *, mode: str = "explore", max_rows: int | None = None) -> dict[str, Any]:
    connector = get_fabric_connector()
    if not connector.is_configured():
        raise FabricConnectionError(
            "Fabric not configured",
            "ยังไม่ได้ตั้งค่า Fabric ใน .env",
        )
    return connector.execute_read_only(sql, mode=mode, max_rows=max_rows or 20)


async def run_fabric_sql_async(
    sql: str, *, mode: str = "explore", max_rows: int | None = None
) -> dict[str, Any]:
    """Run blocking pyodbc work in a thread so slow queries don't freeze the event loop."""
    return await asyncio.to_thread(run_fabric_sql, sql, mode=mode, max_rows=max_rows)


async def get_fabric_schema_text_async(limit: int = 40) -> str:
    return await asyncio.to_thread(get_fabric_schema_text, limit)


def get_fabric_schema_text(limit: int = 40) -> str:
    connector = get_fabric_connector()
    if not connector.is_configured():
        return "(Fabric not configured — set FABRIC_* in .env)"
    rows = connector.fetch_schema_summary(top_schemas=10)
    lines = [
        f"- {r.get('table_schema')}.{r.get('table_name')} ({r.get('table_type')})"
        for r in rows[:limit]
    ]
    return "\n".join(lines) if lines else "(no tables found)"


def format_query_preview(result: dict[str, Any], max_rows: int = 5) -> str:
    rows = result.get("rows", [])[:max_rows]
    if not rows:
        return "(ไม่มีข้อมูล)"
    return json.dumps(rows, ensure_ascii=False, indent=2, default=str)
