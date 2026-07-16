"""CEO feedback store per theme."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.services.local_paths import get_local_dir


def _feedback_path(theme_id: str) -> Path:
    path = get_local_dir() / "feedback"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{theme_id}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_feedback(theme_id: str) -> dict[str, Any]:
    path = _feedback_path(theme_id)
    if not path.exists():
        return {"theme_id": theme_id, "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_feedback(theme_id: str, data: dict[str, Any]) -> dict[str, Any]:
    path = _feedback_path(theme_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return data


def add_feedback(
    theme_id: str,
    *,
    brief_id: str,
    role: str,
    action: str,
    comment: str = "",
    ceo_user: str = "ceo",
) -> dict[str, Any]:
    data = load_feedback(theme_id)
    entry = {
        "id": str(uuid4()),
        "brief_id": brief_id,
        "role": role,
        "action": action,
        "comment": comment,
        "ceo_user": ceo_user,
        "at": _utc_now(),
    }
    data.setdefault("entries", []).append(entry)
    return save_feedback(theme_id, data)


def format_feedback_context(theme_id: str | None) -> str:
    if not theme_id:
        return ""
    data = load_feedback(theme_id)
    entries = data.get("entries", [])
    if not entries:
        return ""
    lines = ["## CEO Feedback (apply to this session)"]
    for e in entries[-10:]:
        lines.append(
            f"- [{e.get('action')}] {e.get('role')}: {e.get('comment', '')}"
        )
    return "\n".join(lines)
