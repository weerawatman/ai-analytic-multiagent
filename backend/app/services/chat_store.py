"""SQLite-backed chat session and message storage."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

from backend.app.core.config import get_settings
from backend.app.services.local_paths import ensure_local_structure, get_local_dir

DB_NAME = "app.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    return get_local_dir() / DB_NAME


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_chat_db() -> None:
    ensure_local_structure()
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                mode TEXT NOT NULL DEFAULT 'explore',
                theme TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                agent TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at);
            """
        )


def ensure_session(
    session_id: str,
    *,
    mode: str = "explore",
    theme: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE sessions
                SET updated_at = ?, mode = COALESCE(?, mode), theme = COALESCE(?, theme)
                WHERE id = ?
                """,
                (now, mode, theme, session_id),
            )
            return dict(conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone())

        conn.execute(
            """
            INSERT INTO sessions (id, title, mode, theme, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, title or session_id[:8], mode, theme, now, now),
        )
        return dict(conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone())


def add_message(
    session_id: str,
    *,
    role: str,
    content: str,
    agent: str | None = None,
    mode: str = "explore",
    theme: str | None = None,
) -> dict[str, Any]:
    ensure_session(session_id, mode=mode, theme=theme)
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (session_id, role, agent, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, agent, content, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.*, COUNT(m.id) AS message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_messages(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
