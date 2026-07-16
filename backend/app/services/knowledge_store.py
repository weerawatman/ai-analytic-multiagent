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


def format_knowledge_context(*, theme: str | None = None) -> str:
    """Sync helper for agent prompts — reads knowledge files (status-filtered)."""
    lines: list[str] = []
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
        lines.append(f"## {label}")
        for item in items[:20]:
            if kind == "glossary":
                lines.append(
                    f"- {item.get('field_key', item.get('id'))}: {item.get('definition_th', '')}"
                )
            elif kind == "targets":
                lines.append(f"- {item.get('name_th', '')}: {item.get('description_th', '')}")
            else:
                lines.append(
                    f"- {item.get('from_table', '')} -> {item.get('to_table', '')} "
                    f"ON {item.get('join_keys', '')}"
                )
    return "\n".join(lines) if lines else "(no knowledge entries yet)"
