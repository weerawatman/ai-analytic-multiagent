"""Remember successful SQL for few-shot retrieval in the DA prompt (Phase J).

Lives in ``analytics.db`` (WAL, INV-7). The "never got a downvote" filter
reads answer_ratings only via ``chat_store.get_downvoted_refs()`` (a
read-only helper that chat_store itself owns) — this module never opens
a connection to the chat database.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.core.logger import logger
from backend.app.services.snapshot_store import get_analytics_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sql_patterns (
    id TEXT PRIMARY KEY,
    theme_id TEXT,
    question TEXT NOT NULL,
    sql TEXT NOT NULL,
    dialect TEXT NOT NULL,
    tables TEXT,
    session_id TEXT,
    message_id INTEGER,
    job_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sql_patterns_dialect
    ON sql_patterns(dialect, created_at DESC);
"""

_TABLE_REF_RE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z0-9_.\[\]\"]+)", re.IGNORECASE)


def init_pattern_tables(db_path: Any = None) -> None:
    with get_analytics_connection(db_path) as conn:
        conn.executescript(_SCHEMA)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_table_refs(sql: str) -> list[str]:
    """Best-effort table-name extraction — supplementary metadata only;
    retrieval below filters on dialect, not on table overlap."""
    seen: list[str] = []
    for m in _TABLE_REF_RE.finditer(sql or ""):
        name = m.group(1).strip('[]"')
        if name.upper() not in ("SELECT",) and name not in seen:
            seen.append(name)
    return seen


def record_pattern(
    *,
    theme_id: str | None,
    question: str,
    sql: str,
    dialect: str,
    tables: list[str] | None = None,
    session_id: str | None = None,
    message_id: int | None = None,
    job_id: str | None = None,
    db_path: Any = None,
) -> str | None:
    """Persist a successfully-executed SQL pattern. Never raises — a failed
    write here must not break the chat turn that just succeeded."""
    if not (question or "").strip() or not (sql or "").strip():
        return None
    import json

    pattern_id = uuid4().hex
    try:
        with get_analytics_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO sql_patterns
                    (id, theme_id, question, sql, dialect, tables, session_id, message_id, job_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern_id,
                    theme_id,
                    question,
                    sql,
                    dialect,
                    json.dumps(tables or extract_table_refs(sql), ensure_ascii=False),
                    session_id,
                    message_id,
                    job_id,
                    _utc_now(),
                ),
            )
        return pattern_id
    except Exception:
        logger.exception("sql_pattern_store: failed to record pattern")
        return None


def _list_candidates(
    *, dialect: str, theme_id: str | None, limit: int, db_path: Any
) -> list[dict[str, Any]]:
    clauses = ["dialect = ?"]
    args: list[Any] = [dialect]
    if theme_id:
        clauses.append("theme_id = ?")
        args.append(theme_id)
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM sql_patterns
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*args, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def _exclude_downvoted(
    candidates: list[dict[str, Any]],
    downvoted_refs: set[tuple[Any, Any, Any]],
) -> list[dict[str, Any]]:
    job_ids = {jid for (_, _, jid) in downvoted_refs if jid}
    session_msgs = {(sid, mid) for (sid, mid, _) in downvoted_refs if mid is not None}
    out = []
    for c in candidates:
        if c.get("job_id") and c["job_id"] in job_ids:
            continue
        if (c.get("session_id"), c.get("message_id")) in session_msgs:
            continue
        out.append(c)
    return out


async def get_similar_patterns(
    question: str,
    *,
    dialect: str,
    theme_id: str | None = None,
    k: int = 3,
    candidate_pool: int = 50,
    db_path: Any = None,
) -> list[dict[str, Any]]:
    """Top-k similar successful patterns, dialect-matched, never-👎'd.

    Falls back to most-recent-first (no ranking) on any embedding error —
    see embedding_service.select_relevant's own fallback contract.
    """
    from backend.app.services.chat_store import get_downvoted_refs
    from backend.app.services.embedding_service import select_relevant

    candidates = _list_candidates(
        dialect=dialect, theme_id=theme_id, limit=candidate_pool, db_path=db_path
    )
    if not candidates:
        return []
    try:
        downvoted = get_downvoted_refs()
        candidates = _exclude_downvoted(candidates, downvoted)
    except Exception:
        logger.warning("sql_pattern_store: could not read downvote refs — skipping filter")
    if not candidates:
        return []
    return await select_relevant(
        question,
        candidates,
        k=k,
        namespace=f"sql_pattern:{dialect}",
        id_key="id",
        text_key="question",
        db_path=db_path,
    )


def format_pattern_context(patterns: list[dict[str, Any]]) -> str:
    if not patterns:
        return ""
    lines = ["## Successful SQL patterns (reuse the approach if relevant to this question)"]
    for i, p in enumerate(patterns, start=1):
        lines.append(f"{i}. Q: {p['question']}\n   SQL: {p['sql']}")
    return "\n".join(lines)
