"""WH_Silver SQL reference loader — inject DDL/load SP into agent context."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.services.local_paths import get_local_dir
from backend.app.services.theme_service import load_cached_themes

_MAX_DDL_CHARS = 4000
_MAX_TABLES = 8


def _sql_ref_root() -> Path:
    return get_local_dir() / "knowledge" / "sql_reference"


def _load_manifest() -> dict[str, Any]:
    path = _sql_ref_root() / "_manifest.json"
    if not path.exists():
        return {"items": []}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalize_ref(ref: str) -> str:
    return ref.strip().lower().replace("[", "").replace("]", "")


def _table_short_name(ref: str) -> str:
    return ref.split(".")[-1]


def _parse_ddl_columns(ddl_text: str) -> list[str]:
    """Extract column names from CREATE TABLE DDL."""
    cols: list[str] = []
    for match in re.finditer(r"\[([^\]]+)\]\s+\w+", ddl_text):
        name = match.group(1)
        if name.upper() not in ("CREATE", "TABLE"):
            cols.append(name)
    return cols


def _read_sql_file(rel_path: str) -> str:
    path = _sql_ref_root() / rel_path.replace("/", "\\")
    if not path.exists():
        path = _sql_ref_root() / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def get_items_for_tables(table_refs: list[str]) -> list[dict[str, Any]]:
    """Match manifest items to Fabric table refs (table_ddl kind first)."""
    manifest = _load_manifest()
    items = manifest.get("items", [])
    if not table_refs:
        return []

    refs_norm = {_normalize_ref(r): r for r in table_refs}
    short_norm = {_normalize_ref(_table_short_name(r)): r for r in table_refs}

    matched: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        if item.get("kind") != "table_ddl":
            continue
        table_ref = item.get("table_ref", "")
        candidates = [
            _normalize_ref(table_ref),
            _normalize_ref(_table_short_name(table_ref)),
        ]
        hit = False
        for c in candidates:
            if c in refs_norm or c in short_norm:
                hit = True
                break
        if hit and item.get("id") not in seen:
            seen.add(item["id"])
            matched.append(item)

    return matched[:_MAX_TABLES]


def get_table_refs_for_theme(theme_id: str | None) -> list[str]:
    if not theme_id:
        return []
    cached = load_cached_themes()
    if not cached:
        return []
    for theme in cached.get("themes", []):
        if theme.get("id") == theme_id:
            return theme.get("sample_tables") or []
    return []


def format_sql_reference_context(
    table_refs: list[str] | None = None,
    *,
    theme_id: str | None = None,
) -> str:
    """Build SQL reference section for agent prompts from synced WH_Silver DDL."""
    refs = table_refs or get_table_refs_for_theme(theme_id)
    if not refs and theme_id:
        refs = get_table_refs_for_theme(theme_id)
    if not refs:
        return "(no sql_reference tables for theme)"

    items = get_items_for_tables(refs)
    if not items:
        return "(sql_reference manifest has no matching table_ddl — run sync-wh-silver-sql.ps1)"

    lines: list[str] = ["## WH_Silver SQL Reference (DDL columns — use these names in SQL)"]
    for item in items:
        table_ref = item.get("table_ref", "")
        rel = item.get("file_path", "")
        ddl = _read_sql_file(rel)
        if not ddl:
            lines.append(f"- {table_ref}: (file missing: {rel})")
            continue
        cols = _parse_ddl_columns(ddl)
        desc = item.get("description_th", "")
        lines.append(f"### {table_ref}")
        if desc:
            lines.append(f"  {desc}")
        if cols:
            preview = ", ".join(cols[:25])
            if len(cols) > 25:
                preview += f", ... (+{len(cols) - 25} more)"
            lines.append(f"  columns: {preview}")
        snippet = ddl[:800].strip()
        if len(ddl) > 800:
            snippet += "\n  ... (truncated)"
        lines.append(f"```sql\n{snippet}\n```")

    text = "\n".join(lines)
    return text[:_MAX_DDL_CHARS * 2] if len(text) > _MAX_DDL_CHARS * 2 else text
