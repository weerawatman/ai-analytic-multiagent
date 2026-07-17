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
from backend.app.services.postgres_replica import get_postgres_connector
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql

# Negative/positive reachability cache: (reachable: bool, expires_at: float)
_reachability_cache: tuple[bool, float] | None = None
# Same TTL-cache shape for the Postgres WH_Silver mirror (auto-fallback source).
_pg_reachability_cache: tuple[bool, float] | None = None

OFFLINE_SQL_MSG_TH = (
    "Fabric ไม่พร้อม (capacity pause / offline) — ข้ามการรัน SQL ใช้ discovery บนดิสก์ + draft SQL"
)

# ORDER BY at paren depth 0 is the outermost one — illegal inside a derived
# table without TOP/OFFSET, so it must be stripped before the COUNT(*) wrap.
_ORDER_BY_RE = re.compile(r"\bORDER\s+BY\b", re.IGNORECASE)
_SELECT_RE = re.compile(r"\bSELECT\b", re.IGNORECASE)
_WITH_RE = re.compile(r"\bWITH\b", re.IGNORECASE)


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


def _skip_leading_ws_comments(sql: str) -> int:
    """Index of the first character past leading whitespace / SQL comments."""
    i = 0
    n = len(sql)
    while i < n:
        if sql[i].isspace():
            i += 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end == -1 else end + 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            break
    return i


def _depth0_match_positions(sql: str, pattern: re.Pattern[str], start: int = 0) -> list[int]:
    """Start indices where `pattern` matches at paren depth 0.

    Skips string literals ('...'), quoted identifiers ("..." — T-SQL
    QUOTED_IDENTIFIER, "" doubles as escape), bracket identifiers ([...]) and
    comments so parentheses/keywords inside them never affect the scan.
    """
    positions: list[int] = []
    depth = 0
    i = start
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'" or ch == '"':
            quote = ch
            i += 1
            while i < n:
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:  # doubled-quote escape
                        i += 2
                        continue
                    break
                i += 1
            i += 1
        elif ch == "[":
            end = sql.find("]", i + 1)
            i = n if end == -1 else end + 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end == -1 else end + 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif ch == "(":
            depth += 1
            i += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
            i += 1
        else:
            if depth == 0:
                match = pattern.match(sql, i)
                if match:
                    positions.append(i)
                    i = match.end()
                    continue
            i += 1
    return positions


def strip_trailing_order_by(sql: str) -> str:
    """Remove only the outermost trailing ORDER BY (plus any OFFSET/FETCH tail).

    Only an ORDER BY at paren depth 0 is stripped — ORDER BY inside subqueries
    (e.g. `SELECT * FROM (SELECT TOP 5 a FROM t ORDER BY a) x`) must survive,
    otherwise the stripped SQL has unbalanced parens and the COUNT guard
    fail-opens on every such query.

    Note (DA finding): when the outer ORDER BY carries OFFSET/FETCH pagination,
    stripping it makes COUNT(*) estimate the full unpaginated set. That is a
    conservative overestimate and acceptable per the Phase D plan (the guard
    would rather over-reject than silently miss an oversized result).
    """
    cleaned = sql.strip().rstrip(";").strip()
    positions = _depth0_match_positions(cleaned, _ORDER_BY_RE)
    if not positions:
        return cleaned
    return cleaned[: positions[-1]].rstrip()


def _split_cte_prefix(sql: str) -> tuple[str, str] | None:
    """Split `WITH ... SELECT ...` into (cte_prefix, final_select).

    Returns None when the query does not start with WITH (after leading
    whitespace/comments) or no depth-0 SELECT is found. CTE bodies live inside
    parens, so the first SELECT at paren depth 0 after the WITH keyword (past
    the comma-separated `name AS (...)` list) is the statement's final SELECT.
    """
    start = _skip_leading_ws_comments(sql)
    with_match = _WITH_RE.match(sql, start)
    if not with_match:
        return None
    select_positions = _depth0_match_positions(sql, _SELECT_RE, start=with_match.end())
    if not select_positions:
        return None
    split = select_positions[0]
    return sql[:split].rstrip(), sql[split:].strip()


def build_count_guard_sql(sql: str) -> str:
    """Wrap a single SELECT/WITH in COUNT(*) after stripping trailing ORDER BY.

    T-SQL forbids `SELECT COUNT(*) FROM (WITH ... SELECT ...)`, so for CTE
    queries the WITH prefix stays outside and only the final SELECT is wrapped.
    """
    inner = strip_trailing_order_by(sql)
    cte_split = _split_cte_prefix(inner)
    if cte_split is not None:
        cte_prefix, final_select = cte_split
        return f"{cte_prefix}\nSELECT COUNT(*) AS cnt FROM (\n{final_select}\n) AS _guard_cnt"
    return f"SELECT COUNT(*) AS cnt FROM (\n{inner}\n) AS _guard_cnt"


def _estimate_row_count_via(sql: str, exec_fn) -> int | None:
    """Shared wrap/execute/parse logic for the pre-flight COUNT(*) guard.

    `exec_fn(count_sql)` executes the wrapped COUNT query against whichever
    connector the caller picked — Fabric-only (`estimate_row_count`) or a
    dispatched source (`estimate_row_count_for_source`). Returns None on
    fail-open (guard itself broken) so callers never block a valid question
    because the guard mechanism failed.
    """
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
        result = exec_fn(count_sql)
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


def estimate_row_count(sql: str, settings: Settings | None = None) -> int | None:
    """Run pre-flight COUNT(*) against Fabric. Returns None on fail-open."""
    return _estimate_row_count_via(
        sql, lambda count_sql: run_fabric_sql(count_sql, mode="row_count_guard", max_rows=1)
    )


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


def estimate_row_count_for_source(sql: str, source: str, settings: Settings | None = None) -> int | None:
    """Run pre-flight COUNT(*) against whichever source is active ('fabric'|'postgres')."""
    return _estimate_row_count_via(
        sql, lambda count_sql: run_sql(count_sql, mode="row_count_guard", max_rows=1, source=source)
    )


async def estimate_row_count_for_source_async(
    sql: str, source: str, settings: Settings | None = None
) -> int | None:
    return await asyncio.to_thread(estimate_row_count_for_source, sql, source, settings)


def enforce_row_count_threshold_for_source(
    sql: str, source: str, settings: Settings | None = None
) -> int | None:
    settings = settings or get_settings()
    estimated = estimate_row_count_for_source(sql, source, settings)
    if estimated is None:
        return None
    threshold = settings.fabric_row_count_threshold
    if estimated > threshold:
        raise RowCountExceeded(estimated=estimated, threshold=threshold)
    return estimated


async def enforce_row_count_threshold_for_source_async(
    sql: str, source: str, settings: Settings | None = None
) -> int | None:
    return await asyncio.to_thread(enforce_row_count_threshold_for_source, sql, source, settings)


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


def clear_pg_reachability_cache() -> None:
    """Test helper — reset TTL cache."""
    global _pg_reachability_cache
    _pg_reachability_cache = None


def mark_pg_unreachable() -> None:
    global _pg_reachability_cache
    ttl = get_settings().fabric_reachability_ttl_seconds
    _pg_reachability_cache = (False, time.monotonic() + ttl)


def mark_pg_reachable() -> None:
    global _pg_reachability_cache
    ttl = get_settings().fabric_reachability_ttl_seconds
    _pg_reachability_cache = (True, time.monotonic() + ttl)


def pg_is_reachable(*, force: bool = False) -> bool:
    """Ping the Postgres replica with TTL cache — same shape as fabric_is_reachable."""
    global _pg_reachability_cache
    connector = get_postgres_connector()
    if not connector.is_configured():
        return False

    now = time.monotonic()
    if not force and _pg_reachability_cache is not None:
        reachable, expires_at = _pg_reachability_cache
        if now < expires_at:
            return reachable

    try:
        connector.ping()
        mark_pg_reachable()
        return True
    except Exception as exc:
        logger.warning("Postgres replica reachability check failed: %s", exc)
        mark_pg_unreachable()
        return False


def pg_can_query() -> bool:
    """True only when SQL against the Postgres replica should be attempted."""
    return pg_is_reachable()


def get_active_sql_source() -> str:
    """Which connector should execute SQL right now: 'fabric' | 'postgres' | 'offline'.

    Fabric is always preferred; the Postgres WH_Silver mirror is the
    auto-fallback when Fabric is unreachable/paused/disabled. Callers use this
    to pick the SQL dialect *before* generating SQL (T-SQL vs PostgreSQL) —
    the two dialects are not interchangeable, so the source must be decided
    up front rather than translated after a query is already written.
    """
    if fabric_can_query():
        return "fabric"
    if pg_can_query():
        return "postgres"
    return "offline"


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


def run_sql(
    sql: str, *, mode: str = "explore", max_rows: int | None = None, source: str = "fabric"
) -> dict[str, Any]:
    """Dispatch a query to whichever source the caller decided on (get_active_sql_source()).

    Callers must generate `sql` in the matching dialect *before* calling this
    — Fabric (T-SQL) and Postgres are not interchangeable at the syntax level.
    """
    if source == "postgres":
        connector = get_postgres_connector()
        try:
            result = connector.execute_read_only(sql, mode=mode, max_rows=max_rows or 20)
            mark_pg_reachable()
        except Exception:
            mark_pg_unreachable()
            raise
        result["source"] = "postgres"
        return result
    result = run_fabric_sql(sql, mode=mode, max_rows=max_rows)
    result["source"] = "fabric"
    return result


async def run_sql_async(
    sql: str, *, mode: str = "explore", max_rows: int | None = None, source: str = "fabric"
) -> dict[str, Any]:
    return await asyncio.to_thread(run_sql, sql, mode=mode, max_rows=max_rows, source=source)


async def get_fabric_schema_text_async(limit: int = 40) -> str:
    return await asyncio.to_thread(get_fabric_schema_text, limit)


def _format_schema_rows(rows: list[dict[str, Any]], limit: int) -> str:
    lines = [
        f"- {r.get('table_schema')}.{r.get('table_name')} ({r.get('table_type')})"
        for r in rows[:limit]
    ]
    return "\n".join(lines) if lines else "(no tables found)"


def get_fabric_schema_text(limit: int = 40) -> str:
    """Schema summary text — Fabric preferred, Postgres replica auto-fallback.

    The replica mirrors Fabric 1:1, so when Fabric is unreachable/paused the
    schema listing still comes from live data instead of dropping straight to
    the disk-cache-only message.
    """
    fabric_connector = get_fabric_connector()
    pg_connector = get_postgres_connector()
    if not fabric_connector.is_configured() and not pg_connector.is_configured():
        return "(Fabric not configured — set FABRIC_* in .env)"

    if fabric_can_query():
        try:
            rows = fabric_connector.fetch_schema_summary(top_schemas=10)
            mark_fabric_reachable()
            return _format_schema_rows(rows, limit)
        except Exception as exc:
            logger.warning("Live Fabric schema fetch failed: %s", exc)
            mark_fabric_unreachable()

    if pg_can_query():
        try:
            rows = pg_connector.fetch_schema_summary(top_schemas=10)
            mark_pg_reachable()
            return _format_schema_rows(rows, limit)
        except Exception as exc:
            logger.warning("Postgres replica schema fetch failed: %s", exc)
            mark_pg_unreachable()

    return f"({OFFLINE_SQL_MSG_TH})"


def format_query_preview(result: dict[str, Any], max_rows: int = 5) -> str:
    rows = result.get("rows", [])[:max_rows]
    if not rows:
        return "(ไม่มีข้อมูล)"
    return json.dumps(rows, ensure_ascii=False, indent=2, default=str)
