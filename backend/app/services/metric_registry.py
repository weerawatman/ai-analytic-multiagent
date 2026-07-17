"""Executable Metric Registry — versioned, dialect-aware KPI definitions (Phase G2).

Canonical home for KPI formulas. Approved entries enter agent prompts;
scheduled pipelines (Phase H+) render SQL via ``render_metric_sql`` only —
never via LLM.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from backend.app.services.local_paths import get_local_dir

_lock = asyncio.Lock()

REGISTRY_FILENAME = "metric_registry.json"
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_EXPR_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

SourceName = Literal["fabric", "postgres", "offline"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _registry_path() -> Path:
    path = get_local_dir() / "knowledge"
    path.mkdir(parents=True, exist_ok=True)
    return path / REGISTRY_FILENAME


def _empty_doc() -> dict[str, Any]:
    return {"version": "1.0", "metrics": []}


async def _read() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _empty_doc()
    text = await asyncio.to_thread(path.read_text, "utf-8")
    return json.loads(text)


async def _write(data: dict[str, Any]) -> None:
    path = _registry_path()
    tmp = path.with_suffix(".tmp")
    content = json.dumps(data, indent=2, ensure_ascii=False)
    await asyncio.to_thread(tmp.write_text, content, "utf-8")
    await asyncio.to_thread(tmp.replace, path)


def _quote_ident(name: str, source: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    if source == "postgres":
        return f'"{name}"'
    return f"[{name}]"


def _quote_table(table: str, source: str) -> str:
    """Quote schema.table for the active dialect."""
    parts = [p for p in table.replace("[", "").replace("]", "").replace('"', "").split(".") if p]
    if not parts:
        raise ValueError(f"Invalid table ref: {table!r}")
    return ".".join(_quote_ident(p, source) for p in parts)


def _cast_measure(expr_or_col: str, source: str) -> str:
    """Wrap bare column refs in CAST(... AS DECIMAL(18,2)); leave expressions alone if already cast."""
    text = expr_or_col.strip()
    if text.upper().startswith("CAST("):
        return text
    # Simple column → cast; complex expression → cast each identifier
    if _IDENT_RE.match(text):
        q = _quote_ident(text, source)
        return f"CAST({q} AS DECIMAL(18,2))"
    # Rewrite bare identifiers inside arithmetic expressions
    def _repl(m: re.Match[str]) -> str:
        ident = m.group(0)
        upper = ident.upper()
        if upper in {"CAST", "AS", "DECIMAL", "SUM", "AVG", "COUNT", "MIN", "MAX", "NULL"}:
            return ident
        return f"CAST({_quote_ident(ident, source)} AS DECIMAL(18,2))"

    return _EXPR_IDENT_RE.sub(_repl, text)


def render_metric_sql(
    entry: dict[str, Any],
    source: str,
    *,
    months: list[str] | None = None,
    dimension: str | None = None,
    limit: int | None = 12,
) -> str:
    """Render a deterministic SELECT for a base (non-derived) metric entry.

    Derived metrics (ratio / period_delta) are computed in Python from snapshots
    in Phase H — this renderer only handles SQL-backed aggregations.
    """
    if entry.get("derived"):
        raise ValueError(
            f"Metric {entry.get('metric_key')} is derived — compute in Python, not SQL"
        )
    if source == "offline":
        raise ValueError("Cannot render SQL for offline source")

    table = _quote_table(entry["table"], source)
    time_col = _quote_ident(entry.get("time_column") or "SourceMonth", source)
    expression = entry.get("expression") or ""
    agg = (entry.get("aggregation") or "SUM").upper()
    if agg not in {"SUM", "AVG", "COUNT", "MIN", "MAX"}:
        raise ValueError(f"Unsupported aggregation: {agg}")

    if agg == "COUNT":
        if expression and _IDENT_RE.match(expression.strip()):
            measure = f"DISTINCT {_quote_ident(expression.strip(), source)}"
        else:
            measure = "*"
        agg_expr = f"COUNT({measure})"
    else:
        measure = _cast_measure(expression, source)
        agg_expr = f"{agg}({measure})"

    select_parts = [f"{agg_expr} AS metric_value"]
    group_parts: list[str] = []

    if dimension:
        dim_q = _quote_ident(dimension, source)
        select_parts.insert(0, f"{dim_q} AS dim_value")
        group_parts.append(dim_q)

    # Always expose period when filtering/grouping by time
    select_parts.insert(0 if not dimension else 1, f"{time_col} AS period")
    group_parts.append(time_col)

    where_clauses: list[str] = []
    if months:
        quoted = ", ".join("'" + m.replace("'", "''") + "'" for m in months)
        where_clauses.append(f"{time_col} IN ({quoted})")

    sql = f"SELECT {', '.join(select_parts)} FROM {table}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if group_parts:
        sql += " GROUP BY " + ", ".join(group_parts)
    sql += f" ORDER BY {time_col} DESC"
    if limit is not None and limit > 0:
        if source == "postgres":
            sql += f" LIMIT {int(limit)}"
        else:
            # T-SQL: inject TOP after SELECT
            sql = sql.replace("SELECT ", f"SELECT TOP {int(limit)} ", 1)
    return sql


def _visible_to_prompts(entry: dict[str, Any]) -> bool:
    status = entry.get("status", "draft")
    if status in ("rejected", "deprecated"):
        return False
    if status == "approved":
        return True
    return entry.get("source") in ("owner_seed", "glossary_migrate")


async def list_metrics(
    *,
    theme: str | None = None,
    status: str | None = None,
    approved_only: bool = False,
) -> list[dict[str, Any]]:
    async with _lock:
        doc = await _read()
    items = list(doc.get("metrics") or [])
    if theme:
        items = [m for m in items if m.get("theme") == theme or not m.get("theme")]
    if approved_only:
        items = [m for m in items if m.get("status") == "approved"]
    elif status:
        items = [m for m in items if m.get("status") == status]
    return items


async def get_metric(metric_key: str) -> dict[str, Any] | None:
    async with _lock:
        doc = await _read()
    for m in doc.get("metrics") or []:
        if m.get("metric_key") == metric_key:
            return m
    return None


async def upsert_metric(entry: dict[str, Any]) -> dict[str, Any]:
    entry = dict(entry)
    change_reason = entry.pop("change_reason", None)
    key = entry.get("metric_key")
    if not key:
        raise ValueError("metric_key is required")
    async with _lock:
        doc = await _read()
        metrics = doc.setdefault("metrics", [])
        now = _utc_now()
        for i, existing in enumerate(metrics):
            if existing.get("metric_key") != key:
                continue
            merged = {**existing, **entry}
            if existing.get("status") == "approved" and merged.get("status") == "draft":
                merged["status"] = "approved"
            # bump version on expression/derived change
            if (
                existing.get("expression") != merged.get("expression")
                or existing.get("derived") != merged.get("derived")
            ):
                merged["version"] = int(existing.get("version") or 1) + 1
                history = list(merged.get("history") or [])
                history.append(
                    {
                        "version": merged["version"],
                        "changed_at": now,
                        "reason": change_reason or "update",
                    }
                )
                merged["history"] = history
            merged["updated_at"] = now
            metrics[i] = merged
            doc["metrics"] = metrics
            await _write(doc)
            return merged

        new_entry = {
            "version": 1,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "history": [{"version": 1, "changed_at": now, "reason": "seed"}],
            **entry,
        }
        metrics.append(new_entry)
        doc["metrics"] = metrics
        await _write(doc)
        return new_entry


async def approve_metric(metric_key: str) -> dict[str, Any]:
    async with _lock:
        doc = await _read()
        for i, m in enumerate(doc.get("metrics") or []):
            if m.get("metric_key") == metric_key:
                m["status"] = "approved"
                m["owner_confirmed"] = True
                m["updated_at"] = _utc_now()
                doc["metrics"][i] = m
                await _write(doc)
                return m
    raise KeyError(f"Metric not found: {metric_key}")


async def deprecate_metric(metric_key: str, reason: str = "") -> dict[str, Any]:
    async with _lock:
        doc = await _read()
        for i, m in enumerate(doc.get("metrics") or []):
            if m.get("metric_key") == metric_key:
                m["status"] = "deprecated"
                m["updated_at"] = _utc_now()
                if reason:
                    history = list(m.get("history") or [])
                    history.append(
                        {"version": m.get("version"), "changed_at": m["updated_at"], "reason": reason}
                    )
                    m["history"] = history
                doc["metrics"][i] = m
                await _write(doc)
                return m
    raise KeyError(f"Metric not found: {metric_key}")


def format_metric_registry_context(
    theme: str | None = None,
    *,
    max_chars: int = 4000,
) -> str:
    """Sync helper for agent prompts — approved metrics only."""
    path = _registry_path()
    if not path.exists():
        return ""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    lines = ["## Metric Registry (approved — use these formulas; do not invent)"]
    used = len(lines[0])
    count = 0
    for m in doc.get("metrics") or []:
        if m.get("status") != "approved":
            continue
        if theme and m.get("theme") and m.get("theme") != theme:
            continue
        if m.get("derived"):
            derived = m["derived"]
            block = (
                f"- {m.get('metric_key')}: {m.get('name_th')} / {m.get('name_en')} "
                f"(derived {derived.get('kind')} of={derived.get('of')} over={derived.get('over')})"
            )
        else:
            block = (
                f"- {m.get('metric_key')}: {m.get('name_th')} / {m.get('name_en')}\n"
                f"  table={m.get('table')} agg={m.get('aggregation')} "
                f"expr={m.get('expression')}"
            )
        if used + len(block) + 1 > max_chars:
            break
        lines.append(block)
        used += len(block) + 1
        count += 1
    if count == 0:
        return ""
    return "\n".join(lines)


def load_registry_sync() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _empty_doc()
    return json.loads(path.read_text(encoding="utf-8"))
