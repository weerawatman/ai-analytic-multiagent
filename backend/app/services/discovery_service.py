"""Theme discovery pipeline — column profiling and relationship heuristics."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger
from backend.app.services.fabric_connector import FabricConnectionError, get_fabric_connector
from backend.app.services.local_paths import get_local_dir
from backend.app.services.theme_service import load_cached_themes

KEY_COLUMN_PATTERNS = re.compile(
    r"(^id$|_id$|_key$|^key$|kunnr|matnr|vbeln|bukrs|werks|fkdat|budat|gjahr|monat)",
    re.IGNORECASE,
)


def _discovery_path(theme_id: str) -> Path:
    path = get_local_dir() / "knowledge" / "themes" / theme_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "discovery.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_theme_tables(theme_id: str) -> list[str]:
    """Resolve table names for a theme from cached theme scan."""
    cached = load_cached_themes()
    if not cached:
        return []
    for theme in cached.get("themes", []):
        if theme.get("id") == theme_id:
            return theme.get("sample_tables") or []
    return []


def _parse_table_ref(ref: str) -> tuple[str, str]:
    if "." in ref:
        schema, table = ref.split(".", 1)
        return schema, table
    return "dbo", ref


def _fetch_columns(schema: str, table: str) -> list[dict[str, Any]]:
    connector = get_fabric_connector()
    sql = (
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = '{schema.replace(chr(39), chr(39)+chr(39))}' "
        f"AND TABLE_NAME = '{table.replace(chr(39), chr(39)+chr(39))}' "
        "ORDER BY ORDINAL_POSITION"
    )
    result = connector.execute_read_only(sql, mode="discovery", max_rows=500)
    return result.get("rows", [])


def _profile_table(schema: str, table: str) -> dict[str, Any]:
    connector = get_fabric_connector()
    full_name = f"{schema}.{table}"
    profile: dict[str, Any] = {
        "table": full_name,
        "schema": schema,
        "table_name": table,
        "columns": [],
        "row_count": None,
        "sample_rows": [],
        "date_columns": [],
    }

    try:
        cols = _fetch_columns(schema, table)
        profile["columns"] = cols
        profile["date_columns"] = [
            c["COLUMN_NAME"]
            for c in cols
            if "date" in str(c.get("DATA_TYPE", "")).lower()
            or "time" in str(c.get("DATA_TYPE", "")).lower()
        ]
    except Exception as exc:
        logger.warning("Column fetch failed for %s: %s", full_name, exc)
        profile["error"] = str(exc)
        return profile

    try:
        count_sql = f"SELECT COUNT(*) AS cnt FROM [{schema}].[{table}]"
        count_result = connector.execute_read_only(count_sql, mode="discovery", max_rows=1)
        if count_result.get("rows"):
            profile["row_count"] = count_result["rows"][0].get("cnt")
    except Exception as exc:
        logger.warning("Row count failed for %s: %s", full_name, exc)

    try:
        sample_sql = f"SELECT TOP 3 * FROM [{schema}].[{table}]"
        sample_result = connector.execute_read_only(sample_sql, mode="discovery", max_rows=3)
        profile["sample_rows"] = sample_result.get("rows", [])
    except Exception as exc:
        logger.warning("Sample fetch failed for %s: %s", full_name, exc)

    return profile


def _detect_relationships(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Heuristic: columns matching key patterns shared across tables."""
    col_map: dict[str, list[str]] = defaultdict(list)
    for p in profiles:
        table = p.get("table", "")
        for col in p.get("columns", []):
            name = str(col.get("COLUMN_NAME", ""))
            if KEY_COLUMN_PATTERNS.search(name):
                col_map[name.upper()].append(table)

    relationships: list[dict[str, Any]] = []
    for col, tables in col_map.items():
        if len(tables) >= 2:
            relationships.append(
                {
                    "column": col,
                    "tables": tables,
                    "confidence": "medium",
                    "note": f"Shared key candidate: {col}",
                }
            )
    return relationships


def run_discovery(theme_id: str, *, table_refs: list[str] | None = None) -> dict[str, Any]:
    """Run full discovery for a theme and persist results."""
    connector = get_fabric_connector()
    if not connector.is_configured():
        raise FabricConnectionError("Fabric not configured", "ยังไม่ได้ตั้งค่า Fabric ใน .env")

    refs = table_refs or get_theme_tables(theme_id)
    if not refs:
        raise ValueError(f"No tables found for theme {theme_id}")

    profiles: list[dict[str, Any]] = []
    for ref in refs[:12]:
        schema, table = _parse_table_ref(ref)
        profiles.append(_profile_table(schema, table))

    relationships = _detect_relationships(profiles)

    payload = {
        "theme_id": theme_id,
        "discovered_at": _utc_now(),
        "database": connector.settings.fabric_database,
        "tables_profiled": len(profiles),
        "profiles": profiles,
        "relationships": relationships,
    }

    path = _discovery_path(theme_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)
    logger.info("Discovery saved for theme %s (%d tables)", theme_id, len(profiles))
    return payload


def load_discovery(theme_id: str) -> dict[str, Any] | None:
    path = _discovery_path(theme_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def format_schema_context_pack(theme_id: str | None = None, limit_cols: int = 80) -> str:
    """Build rich schema text with columns for agent prompts."""
    if not theme_id:
        from backend.app.services.fabric_sql import get_fabric_schema_text
        return get_fabric_schema_text()

    discovery = load_discovery(theme_id)
    if not discovery:
        from backend.app.services.fabric_sql import get_fabric_schema_text
        return get_fabric_schema_text()

    lines: list[str] = []
    col_count = 0
    for profile in discovery.get("profiles", []):
        table = profile.get("table", "")
        rows = profile.get("row_count", "?")
        lines.append(f"## {table} (rows: {rows})")
        for col in profile.get("columns", []):
            if col_count >= limit_cols:
                break
            lines.append(
                f"  - {col.get('COLUMN_NAME')} ({col.get('DATA_TYPE')})"
            )
            col_count += 1
        if profile.get("date_columns"):
            lines.append(f"  date_columns: {', '.join(profile['date_columns'])}")
        lines.append("")

    rels = discovery.get("relationships", [])
    if rels:
        lines.append("## Likely relationships")
        for r in rels[:10]:
            lines.append(f"  - {r['column']}: {', '.join(r['tables'])}")

    return "\n".join(lines) if lines else "(no discovery data)"


def get_columns_for_table(theme_id: str, table_ref: str) -> list[str]:
    discovery = load_discovery(theme_id)
    if not discovery:
        return []
    for profile in discovery.get("profiles", []):
        if profile.get("table", "").lower() == table_ref.lower():
            return [str(c.get("COLUMN_NAME", "")) for c in profile.get("columns", [])]
    return []
