"""Structured knowledge store — glossary, targets, relationships."""

from __future__ import annotations

import json
import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.services.local_paths import get_local_dir

_lock = asyncio.Lock()

_FILES = {
    "glossary": "glossary.json",
    "targets": "targets.json",
    "relationships": "relationships.json",
}

_NATURAL_KEYS = {
    "glossary": ("field_key",),
    "targets": ("name_th",),
    "relationships": ("from_table", "to_table", "join_keys"),
}


def _knowledge_dir() -> Path:
    path = get_local_dir() / "knowledge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _empty_list_doc() -> dict[str, Any]:
    return {"version": "1.0", "items": []}


def _path_for(kind: str) -> Path:
    return _knowledge_dir() / _FILES[kind]


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def _visible_to_prompts(item: dict[str, Any]) -> bool:
    """Filter for agent prompts only — Knowledge panel still lists everything."""
    status = item.get("status", "draft")
    if status == "rejected":
        return False
    if status == "approved":
        return True
    # draft/other: hide machine-sourced until HITL approve
    return item.get("source") not in ("ceo_feedback", "consultant")


async def _read(kind: str) -> dict[str, Any]:
    path = _path_for(kind)
    if not path.exists():
        return _empty_list_doc()
    text = await asyncio.to_thread(path.read_text, "utf-8")
    return json.loads(text)


async def _write(kind: str, data: dict[str, Any]) -> None:
    path = _path_for(kind)
    tmp = path.with_suffix(".tmp")
    content = json.dumps(data, indent=2, ensure_ascii=False)
    await asyncio.to_thread(tmp.write_text, content, "utf-8")
    await asyncio.to_thread(tmp.replace, path)


async def list_items(kind: str, *, theme: str | None = None) -> list[dict[str, Any]]:
    async with _lock:
        doc = await _read(kind)
    items = doc.get("items", [])
    if theme:
        items = [i for i in items if i.get("theme") == theme or not i.get("theme")]
    return items


async def add_item(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    async with _lock:
        doc = await _read(kind)
        new_item = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft",
            **item,
        }
        doc.setdefault("items", []).append(new_item)
        await _write(kind, doc)
        return new_item


def _keys_match(kind: str, existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    keys = _NATURAL_KEYS.get(kind, ())
    if not keys:
        return False
    if _norm(existing.get("theme")) != _norm(incoming.get("theme")):
        return False
    return all(_norm(existing.get(k)) == _norm(incoming.get(k)) for k in keys)


async def upsert_item(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    """Match on normalized natural keys + theme; update in place or add.

    Never downgrade status approved → draft.
    """
    async with _lock:
        doc = await _read(kind)
        items = doc.setdefault("items", [])
        for i, existing in enumerate(items):
            if not _keys_match(kind, existing, item):
                continue
            merged = {**existing, **item}
            # Protect approved status from accidental downgrade
            if existing.get("status") == "approved" and merged.get("status") == "draft":
                merged["status"] = "approved"
            merged["id"] = existing["id"]
            merged["created_at"] = existing.get("created_at") or merged.get("created_at")
            merged["updated_at"] = datetime.now(timezone.utc).isoformat()
            items[i] = merged
            doc["items"] = items
            await _write(kind, doc)
            return merged

    return await add_item(kind, item)


async def update_item(kind: str, item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    async with _lock:
        doc = await _read(kind)
        items = doc.get("items", [])
        for i, item in enumerate(items):
            if item.get("id") == item_id:
                item.update(updates)
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                items[i] = item
                doc["items"] = items
                await _write(kind, doc)
                return item
        raise KeyError(f"Item not found: {item_id}")


# Prompt budget for the knowledge section. The old flat 20-items/kind cap
# silently dropped owner-verified column mappings (VVA02–VVA22 → cleaned
# columns) once metric/table entries filled the head of the list. Budgeting
# is now by *category priority* under a char cap so metric formulas AND
# table roles AND column mappings all reach the agents predictably.
_KNOWLEDGE_CHAR_BUDGET = 9000

# Priority buckets for glossary entries: metric definitions carry business
# formulas (must never be cut), table entries carry roles/aliases, the rest
# are column-level mappings that fill the remaining budget.
_GLOSSARY_BUCKETS = ("metric", "table", "column")


def _glossary_bucket(item: dict[str, Any]) -> str:
    key = str(item.get("field_key") or "")
    if key.startswith("metric."):
        return "metric"
    if key.startswith("table."):
        return "table"
    return "column"


def _status_rank(item: dict[str, Any]) -> int:
    return 0 if item.get("status") == "approved" else 1


def _glossary_lines_budgeted(items: list[dict[str, Any]]) -> list[str]:
    """Order glossary entries metric → table → column (approved first in each)."""
    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in _GLOSSARY_BUCKETS}
    for item in items:
        buckets[_glossary_bucket(item)].append(item)
    ordered: list[dict[str, Any]] = []
    for bucket in _GLOSSARY_BUCKETS:
        ordered.extend(sorted(buckets[bucket], key=_status_rank))
    return [
        f"- {i.get('field_key', i.get('id'))}: {i.get('definition_th', '')}" for i in ordered
    ]


def aggregate_approved_knowledge(
    *,
    theme: str | None = None,
    include_lessons: bool = True,
) -> dict[str, Any]:
    """Cross-theme aggregation: global layer + per-theme override (Phase K).

    Precedence: theme-specific approved item wins over global (no theme) on the
    same natural key. Draft/rejected items are excluded. SQL lessons from
    ``sql_lessons.json`` are attached as a global layer (no per-theme override).
    """
    kinds = ("glossary", "targets", "relationships")
    layers: dict[str, list[dict[str, Any]]] = {k: [] for k in kinds}

    for kind in kinds:
        path = _path_for(kind)
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        items = [i for i in doc.get("items", []) if i.get("status") == "approved"]
        global_items = [i for i in items if not i.get("theme")]
        theme_items = [i for i in items if theme and i.get("theme") == theme]

        # Index by natural key; theme overrides global
        merged: dict[str, dict[str, Any]] = {}
        for item in global_items:
            key_parts = [_norm(item.get(k)) for k in _NATURAL_KEYS.get(kind, ("id",))]
            merged["|".join(key_parts)] = {**item, "layer": "global"}
        for item in theme_items:
            key_parts = [_norm(item.get(k)) for k in _NATURAL_KEYS.get(kind, ("id",))]
            merged["|".join(key_parts)] = {**item, "layer": "theme_override"}
        layers[kind] = list(merged.values())

    lessons: list[dict[str, Any]] = []
    if include_lessons:
        try:
            from backend.app.services import lesson_miner

            lessons = [
                {**L, "layer": "global", "status": "available"}
                for L in lesson_miner.load_lessons()
            ]
        except Exception:
            lessons = []

    return {
        "version": "1.0",
        "theme": theme,
        "precedence": "theme_override > global",
        "glossary": layers["glossary"],
        "targets": layers["targets"],
        "relationships": layers["relationships"],
        "lessons": lessons,
        "counts": {
            "glossary": len(layers["glossary"]),
            "targets": len(layers["targets"]),
            "relationships": len(layers["relationships"]),
            "lessons": len(lessons),
        },
    }


def format_knowledge_context(*, theme: str | None = None) -> str:
    """Sync helper for agent prompts — reads knowledge files (status-filtered).

    Glossary entries are budgeted by category (metric formulas first, then
    table roles, then column mappings) under a total char budget instead of a
    flat per-kind item cap, so verified definitions reach agents predictably.
    """
    sections: list[tuple[str, list[str]]] = []
    for kind, label in [("glossary", "Glossary"), ("targets", "Targets"), ("relationships", "Relationships")]:
        path = _path_for(kind)
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        items = doc.get("items", [])
        if theme:
            items = [i for i in items if not i.get("theme") or i.get("theme") == theme]
        items = [i for i in items if _visible_to_prompts(i)]
        if not items:
            continue
        if kind == "glossary":
            entry_lines = _glossary_lines_budgeted(items)
        elif kind == "targets":
            entry_lines = [
                f"- {i.get('name_th', '')}: {i.get('description_th', '')}" for i in items[:20]
            ]
        else:
            entry_lines = [
                f"- {i.get('from_table', '')} -> {i.get('to_table', '')} "
                f"ON {i.get('join_keys', '')}"
                for i in items[:20]
            ]
        sections.append((label, entry_lines))

    if not sections:
        return "(no knowledge entries yet)"

    # Reserve space for targets/relationships first (they are small), then let
    # glossary fill whatever remains of the budget.
    lines: list[str] = []
    non_glossary_chars = sum(
        len(line) + 1 for label, entry_lines in sections if label != "Glossary" for line in entry_lines
    )
    glossary_budget = max(_KNOWLEDGE_CHAR_BUDGET - non_glossary_chars, 3000)
    for label, entry_lines in sections:
        lines.append(f"## {label}")
        if label == "Glossary":
            used = 0
            dropped = 0
            for line in entry_lines:
                if used + len(line) + 1 > glossary_budget:
                    dropped += 1
                    continue
                lines.append(line)
                used += len(line) + 1
            if dropped:
                lines.append(f"- … (+{dropped} column entries omitted for prompt budget)")
        else:
            lines.extend(entry_lines)
    return "\n".join(lines)
