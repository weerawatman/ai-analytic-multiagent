"""Helpers for Fabric SQL execution and schema preview."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from backend.app.core.config import Settings, get_settings
from backend.app.core.logger import logger
from backend.app.services.fabric_connector import FabricConnectionError, get_fabric_connector
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql

# Negative/positive reachability cache: (reachable: bool, expires_at: float)
_reachability_cache: tuple[bool, float] | None = None

OFFLINE_SQL_MSG_TH = (
    "Fabric ไม่พร้อม (capacity pause / offline) — ข้ามการรัน SQL ใช้ discovery บนดิสก์ + draft SQL"
)

# Trailing ORDER BY (and optional OFFSET/FETCH) — illegal inside a derived table without TOP.
_TRAILING_ORDER_BY = re.compile(r"\s+ORDER\s+BY\b[\s\S]*$", re.IGNORECASE)


class RowCountExceeded(Exception):
    """Pre-flight COUNT(*) exceeded fabric_row_count_threshold."""

    def __init__(self, estimated: int, threshold: int) -> None:
        self.estimated = estimated
        self.threshold = threshold
        message = (
            f"Estimated row count {estimated} exceeds threshold {threshold}. "
            "Narrow the query with WHERE filters (date range, org unit, etc.)."
        )
        message_th = (
            f"จำนวนแถวโดยประมาณ {estimated:,} เกินเกณฑ์ {threshold:,} — "
            "กรุณาจำกัดด้วย WHERE (ช่วงเวลา/หน่วยงาน/เงื่อนไข)"
        )
        super().__init__(message)
        self.message_th = message_th


def strip_trailing_order_by(sql: str) -> str:
    """Remove trailing ORDER BY so the query can be wrapped in a derived table."""
    cleaned = sql.strip().rstrip(";").strip()
    return _TRAILING_ORDER_BY.sub("", cleaned).strip()


def build_count_guard_sql(sql: str) -> str:
    """Wrap a single SELECT/WITH in COUNT(*) after stripping trailing ORDER BY."""
    inner = strip_trailing_order_by(sql)
    return f"SELECT COUNT(*) AS cnt FROM (\n{inner}\n) AS _guard_cnt"


def estimate_row_count(sql: str, settings: Settings | None = None) -> int | None:
    """Run pre-flight COUNT(*). Returns None on fail-open (guard itself broken)."""
    settings = settings or get_settings()
    try:
        safe_sql = validate_read_only_sql(sql)
    except SQLGuardError as exc:
        logger.warning("Row-count guard skipped — SQL guard rejected query: %s", exc)
        return None

    try:
        count_sql = build_count_guard_sql(safe_sql)
        # Re-validate the wrapped form (still SELECT-only).
        count_sql = validate_read_only_sql(count_sql)
    except Exception as exc:
        logger.warning("Row-count guard fail-open (wrap failed): %s", exc)
        return None

    started = time.monotonic()
    try:
        result = run_fabric_sql(count_sql, mode="row_count_guard", max_rows=1)
    except Exception as exc:
        logger.warning("Row-count guard fail-open (count query failed): %s", exc)
        return None

    elapsed_ms = int((time.monotonic() - started) * 1000)
    rows = result.get("rows") or []
    if not rows:
        logger.warning("Row-count guard fail-open (empty count result) in %sms", elapsed_ms)
        return None

    raw = rows[0].get("cnt", next(iter(rows[0].values()), None))
    try:
        estimated = int(raw)
    except (TypeError, ValueError):
        logger.warning("Row-count guard fail-open (non-int count=%r) in %sms", raw, elapsed_ms)
        return None

    logger.info("Row-count pre-flight estimated=%s in %sms", estimated, elapsed_ms)
    return estimated


async def estimate_row_count_async(sql: str, settings: Settings | None = None) -> int | None:
    return await asyncio.to_thread(estimate_row_count, sql, settings)


def enforce_row_count_threshold(sql: str, settings: Settings | None = None) -> int | None:
    """Estimate rows; raise RowCountExceeded when over threshold. None = fail-open."""
    settings = settings or get_settings()
    estimated = estimate_row_count(sql, settings)
    if estimated is None:
        return None
    threshold = settings.fabric_row_count_threshold
    if estimated > threshold:
        raise RowCountExceeded(estimated=estimated, threshold=threshold)
    return estimated


async def enforce_row_count_threshold_async(
    sql: str, settings: Settings | None = None
) -> int | None:
    return await asyncio.to_thread(enforce_row_count_threshold, sql, settings)


def fabric_is_available() -> bool:
    """True when FABRIC_* credentials are configured (does not mean warehouse is reachable)."""
    return get_fabric_connector().is_configured()


def clear_reachability_cache() -> None:
    """Test helper — reset TTL cache."""
    global _reachability_cache
    _reachability_cache = None


def mark_fabric_unreachable() -> None:
    """Remember that live Fabric failed (e.g. after SQL/connect error)."""
    global _reachability_cache
    ttl = get_settings().fabric_reachability_ttl_seconds
    _reachability_cache = (False, time.monotonic() + ttl)


def mark_fabric_reachable() -> None:
    global _reachability_cache
    ttl = get_settings().fabric_reachability_ttl_seconds
    _reachability_cache = (True, time.monotonic() + ttl)


def fabric_is_reachable(*, force: bool = False) -> bool:
    """Ping Fabric with TTL cache — failed ping is cached to avoid repeated long timeouts."""
    global _reachability_cache
    connector = get_fabric_connector()
    if not connector.is_configured():
        return False

    now = time.monotonic()
    if not force and _reachability_cache is not None:
        reachable, expires_at = _reachability_cache
        if now < expires_at:
            return reachable

    try:
        connector.ping()
        mark_fabric_reachable()
        return True
    except Exception as exc:
        logger.warning("Fabric reachability check failed: %s", exc)
        mark_fabric_unreachable()
        return False


def fabric_can_query() -> bool:
    """True only when SQL against Fabric should be attempted."""
    settings = get_settings()
    if not settings.fabric_sql_enabled:
        return False
    if not fabric_is_available():
        return False
    return fabric_is_reachable()


def run_fabric_sql(sql: str, *, mode: str = "explore", max_rows: int | None = None) -> dict[str, Any]:
    connector = get_fabric_connector()
    if not connector.is_configured():
        raise FabricConnectionError(
            "Fabric not configured",
            "ยังไม่ได้ตั้งค่า Fabric ใน .env",
        )
    if not get_settings().fabric_sql_enabled:
        raise FabricConnectionError(
            "Fabric SQL disabled",
            "FABRIC_SQL_ENABLED=false — ข้ามการรัน SQL",
        )
    try:
        result = connector.execute_read_only(sql, mode=mode, max_rows=max_rows or 20)
        mark_fabric_reachable()
        return result
    except FabricConnectionError:
        mark_fabric_unreachable()
        raise
    except Exception:
        mark_fabric_unreachable()
        raise


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
    if not fabric_can_query():
        return f"({OFFLINE_SQL_MSG_TH})"
    try:
        rows = connector.fetch_schema_summary(top_schemas=10)
        mark_fabric_reachable()
    except Exception as exc:
        logger.warning("Live Fabric schema fetch failed: %s", exc)
        mark_fabric_unreachable()
        return f"(Fabric schema ไม่พร้อม: {type(exc).__name__} — ใช้ discovery บนดิสก์)"
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
