"""SQLite-backed job records for long-running chat/onboarding runs.

Lives in the same data/local/app.db as chat history. All writers run in the
single backend process, so plain read-modify-write on the JSON progress
column is safe.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.services.chat_store import get_connection

ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("done", "failed", "cancelled")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_jobs_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                thread_id TEXT,
                status TEXT NOT NULL,
                question TEXT,
                params TEXT,
                current_step TEXT,
                progress TEXT NOT NULL DEFAULT '[]',
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                heartbeat_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_thread
                ON jobs(thread_id, created_at);
            """
        )
        # Idempotent migration for DBs created before Phase G1.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "heartbeat_at" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN heartbeat_at TEXT")


def touch_job(job_id: str) -> None:
    """Refresh heartbeat_at — called by the runner ticker (~10s) while a job is alive."""
    update_job(job_id, heartbeat_at=_utc_now())


def _row_to_job(row: Any) -> dict[str, Any]:
    job = dict(row)
    job["progress"] = json.loads(job.get("progress") or "[]")
    job["params"] = json.loads(job["params"]) if job.get("params") else {}
    job["result"] = json.loads(job["result"]) if job.get("result") else None
    return job


def create_job(
    kind: str,
    thread_id: str | None,
    question: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    job_id = uuid4().hex
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, kind, thread_id, status, question, params, progress, created_at)
            VALUES (?, ?, ?, 'queued', ?, ?, '[]', ?)
            """,
            (job_id, kind, thread_id, question, json.dumps(params or {}, ensure_ascii=False), _utc_now()),
        )
    return get_job(job_id)  # type: ignore[return-value]


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    serialized: dict[str, Any] = {}
    for key, value in fields.items():
        if key in ("progress", "params", "result") and value is not None and not isinstance(value, str):
            serialized[key] = json.dumps(value, ensure_ascii=False, default=str)
        else:
            serialized[key] = value
    assignments = ", ".join(f"{k} = ?" for k in serialized)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?",
            (*serialized.values(), job_id),
        )


def append_step(job_id: str, step: str) -> None:
    """Mark a step as started in the timeline and set current_step."""
    job = get_job(job_id)
    if job is None:
        return
    progress = job["progress"]
    progress.append(
        {"step": step, "status": "running", "started_at": _utc_now(), "ended_at": None, "note": None}
    )
    update_job(job_id, progress=progress, current_step=step)


def finish_step(job_id: str, step: str, status: str, note: str | None = None) -> None:
    """Close the latest timeline entry for `step` (create one if missing)."""
    job = get_job(job_id)
    if job is None:
        return
    progress = job["progress"]
    entry = next((p for p in reversed(progress) if p["step"] == step), None)
    if entry is None:
        entry = {"step": step, "status": status, "started_at": _utc_now(), "ended_at": None, "note": None}
        progress.append(entry)
    entry["status"] = status
    entry["ended_at"] = _utc_now()
    if note:
        entry["note"] = note[:500]
    update_job(job_id, progress=progress)


def find_active_job(kind: str, thread_id: str | None) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE kind = ? AND thread_id = ? AND status IN ('queued', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (kind, thread_id),
        ).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(
    thread_id: str | None = None,
    kind: str | None = None,
    active_only: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if thread_id:
        clauses.append("thread_id = ?")
        args.append(thread_id)
    if kind:
        clauses.append("kind = ?")
        args.append(kind)
    if active_only:
        clauses.append("status IN ('queued', 'running')")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?",
            (*args, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def fail_orphaned_jobs() -> int:
    """Mark queued/running jobs from a previous process as failed (startup reconciliation)."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                error = 'Backend restarted while the job was running — please ask again',
                finished_at = ?
            WHERE status IN ('queued', 'running')
            """,
            (_utc_now(),),
        )
        return cursor.rowcount


def purge_old_terminal_jobs(older_than_days: int = 14) -> int:
    """Delete terminal jobs (done/failed/cancelled) older than N days. Used by cleanup script."""
    if older_than_days < 1:
        raise ValueError("older_than_days must be >= 1")
    from datetime import timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(older_than_days))).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM jobs
            WHERE status IN ('done', 'failed', 'cancelled')
              AND coalesce(finished_at, created_at) < ?
            """,
            (cutoff,),
        )
        return cursor.rowcount
