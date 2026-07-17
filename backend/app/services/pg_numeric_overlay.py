"""Postgres numeric-column overlay for the WH_Silver mirror (Phase F).

Fabric reports every WH_Silver column as varchar, but the Postgres mirror has
cast a handful of money/rate fields to real numeric types. The Data Analyst's
schema context comes from Fabric discovery only, so when the active source is
the Postgres fallback the DA cannot see which columns are truly numeric there.
This overlay closes that gap: a small JSON mapping (delivered by the data team
per Phase F D-2) is appended to the DA prompt only when source == "postgres".

The mapping lives at data/local/knowledge/pg_numeric_columns.json (seeded from
data/templates/pg_numeric_columns.template.json — VBRK entries were verified
live during the Phase F deep audit). Missing/invalid file = empty overlay;
this must never break the DA path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger
from backend.app.services.local_paths import get_local_dir, get_templates_dir

_OVERLAY_FILENAME = "pg_numeric_columns.json"
_TEMPLATE_FILENAME = "pg_numeric_columns.template.json"


def _overlay_path() -> Path:
    return get_local_dir() / "knowledge" / _OVERLAY_FILENAME


def _template_path() -> Path:
    return get_templates_dir() / _TEMPLATE_FILENAME


def load_pg_numeric_columns() -> dict[str, list[str]]:
    """Return {table_ref: [numeric column, ...]} — {} when nothing is configured.

    Prefers the local file (data team drops the full D-2 mapping there);
    falls back to the repo template (verified VBRK seed) so the overlay works
    out of the box. Any parse/shape problem degrades to {} with a warning —
    the DA path must never fail because this file is malformed.
    """
    for path in (_overlay_path(), _template_path()):
        if not path.exists():
            continue
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            tables = data.get("tables") if isinstance(data, dict) else None
            if not isinstance(tables, dict):
                logger.warning("pg numeric overlay %s has no 'tables' mapping", path.name)
                continue
            cleaned: dict[str, list[str]] = {}
            for table, cols in tables.items():
                if isinstance(cols, list):
                    names = [str(c) for c in cols if str(c).strip()]
                    if names:
                        cleaned[str(table)] = names
            return cleaned
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("pg numeric overlay unreadable (%s): %s", path.name, exc)
    return {}


def format_pg_numeric_context() -> str:
    """Render the overlay as prompt text — empty string when no mapping exists."""
    tables = load_pg_numeric_columns()
    if not tables:
        return ""
    lines = [
        "PostgreSQL mirror numeric columns (these are TRUE numeric types on this "
        "source — no CAST needed; every other column is varchar and MUST be cast "
        "before aggregation/comparison):"
    ]
    for table in sorted(tables):
        lines.append(f"- {table}: {', '.join(tables[table])}")
    return "\n".join(lines)
