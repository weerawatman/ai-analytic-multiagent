"""JSON file-backed insight candidate backlog."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.services.local_paths import ensure_local_structure, get_local_dir

VALID_STATUSES = {"new", "discussing", "validated", "rejected", "promoted"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backlog_dir() -> Path:
    ensure_local_structure()
    return get_local_dir() / "backlog"


def _item_path(item_id: str) -> Path:
    return _backlog_dir() / f"{item_id}.json"


def _read_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_file(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def create_item(payload: dict[str, Any]) -> dict[str, Any]:
    item_id = payload.get("id") or str(uuid4())
    now = _utc_now()
    item = {
        "id": item_id,
        "theme": payload.get("theme", ""),
        "mode": payload.get("mode", "explore"),
        "question_th": payload.get("question_th", ""),
        "answer_summary_th": payload.get("answer_summary_th", ""),
        "sql_primary": payload.get("sql_primary", ""),
        "sql_alternative": payload.get("sql_alternative", ""),
        "assumptions": payload.get("assumptions", []),
        "confidence": payload.get("confidence", "medium"),
        "unknowns": payload.get("unknowns", []),
        "questions_for_ba_da": payload.get("questions_for_ba_da", []),
        "sample_data_ref": payload.get("sample_data_ref", ""),
        # Provenance (Phase F): which source produced the sample/answer —
        # "fabric" | "postgres" (mirror fallback) | "offline".
        "data_source": payload.get("data_source", ""),
        "status": payload.get("status", "new"),
        "ba_da_feedback": payload.get("ba_da_feedback", []),
        "created_at": payload.get("created_at", now),
        "updated_at": now,
    }
    if item["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {item['status']}")

    path = _item_path(item_id)
    _write_file(path, item)
    return item


def list_items(
    *,
    status: str | None = None,
    theme: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_backlog_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            item = _read_file(path)
        except (json.JSONDecodeError, OSError):
            continue
        if status and item.get("status") != status:
            continue
        if theme and item.get("theme") != theme:
            continue
        items.append(item)
    return items


def get_item(item_id: str) -> dict[str, Any] | None:
    path = _item_path(item_id)
    if not path.exists():
        return None
    return _read_file(path)


def update_item(item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    item = get_item(item_id)
    if item is None:
        raise FileNotFoundError(f"Backlog item not found: {item_id}")

    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {updates['status']}")

    if "feedback" in updates and updates["feedback"]:
        feedback_list = item.setdefault("ba_da_feedback", [])
        feedback_list.append(
            {"at": _utc_now(), "note": updates["feedback"]},
        )

    for key in (
        "theme",
        "mode",
        "question_th",
        "answer_summary_th",
        "sql_primary",
        "sql_alternative",
        "assumptions",
        "confidence",
        "unknowns",
        "questions_for_ba_da",
        "sample_data_ref",
        "status",
    ):
        if key in updates and key != "feedback":
            item[key] = updates[key]

    item["updated_at"] = _utc_now()
    _write_file(_item_path(item_id), item)
    return item
