"""Persistent PDCA failure log for SQL (and future Python) retry loops."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.local_paths import get_local_dir


def _pdca_path() -> Path:
    path = get_local_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path / "pdca_failures.jsonl"


def _append_record(record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with _pdca_path().open("a", encoding="utf-8") as f:
        f.write(line)


async def log_sql_failure(
    theme_id: str,
    user_prompt: str,
    sql: str,
    error: str,
    retry_count: int,
) -> None:
    """Append one PDCA failure entry (call on every failed attempt, not only final)."""
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "kind": "sql",
        "theme_id": theme_id or "",
        "user_prompt": user_prompt or "",
        "sql": sql or "",
        "error": error or "",
        "retry_count": retry_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await asyncio.to_thread(_append_record, record)


__all__ = ["log_sql_failure"]
