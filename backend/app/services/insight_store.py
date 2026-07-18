"""SQLite persistence for proactive insights (Phase I).

Lives in the same ``analytics.db`` (WAL) as Phase H snapshots — never touches
the chat job database (INV-7). Pure persistence; scoring/narration logic
lives in ``insight_pipeline.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.services.snapshot_store import get_analytics_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    created_at TEXT NOT NULL,
    theme_id TEXT,
    metric_key TEXT NOT NULL,
    detector TEXT NOT NULL,
    dim_name TEXT NOT NULL,
    dim_value TEXT NOT NULL,
    period TEXT NOT NULL,
    direction TEXT,
    magnitude REAL,
    significance REAL,
    impact REAL,
    novelty REAL,
    score REAL,
    rank_score REAL,
    status TEXT NOT NULL,
    evidence TEXT,
    narrative_th TEXT,
    narrated_at TEXT,
    published_at TEXT,
    source TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS insight_feedback (
    id TEXT PRIMARY KEY,
    insight_id TEXT NOT NULL,
    label TEXT NOT NULL,
    comment TEXT,
    user_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_insights_status_created
    ON insights(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_key_dedupe
    ON insights(metric_key, dim_name, dim_value, direction, status);
CREATE INDEX IF NOT EXISTS idx_insight_feedback_insight
    ON insight_feedback(insight_id);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_insight_tables(db_path: Path | None = None) -> None:
    with get_analytics_connection(db_path) as conn:
        conn.executescript(_SCHEMA)


def _row_to_insight(row: Any) -> dict[str, Any]:
    d = dict(row)
    if d.get("evidence"):
        try:
            d["evidence"] = json.loads(d["evidence"])
        except (TypeError, ValueError):
            pass
    return d


def create_insight(
    *,
    theme_id: str | None,
    metric_key: str,
    detector: str,
    dim_name: str,
    dim_value: str,
    period: str,
    direction: str | None,
    magnitude: float | None,
    significance: float | None,
    impact: float | None,
    novelty: float | None,
    score: float | None,
    rank_score: float | None,
    status: str,
    evidence: dict[str, Any] | None,
    run_id: str | None = None,
    source: str | None = None,
    narrative_th: str | None = None,
    narrated_at: str | None = None,
    published_at: str | None = None,
    expires_at: str | None = None,
    db_path: Path | None = None,
) -> str:
    insight_id = uuid4().hex
    with get_analytics_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO insights (
                id, run_id, created_at, theme_id, metric_key, detector,
                dim_name, dim_value, period, direction, magnitude,
                significance, impact, novelty, score, rank_score,
                status, evidence, narrative_th, narrated_at, published_at,
                source, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                insight_id,
                run_id,
                _utc_now(),
                theme_id,
                metric_key,
                detector,
                dim_name,
                dim_value,
                period,
                direction,
                magnitude,
                significance,
                impact,
                novelty,
                score,
                rank_score,
                status,
                json.dumps(evidence, ensure_ascii=False, default=str) if evidence is not None else None,
                narrative_th,
                narrated_at,
                published_at,
                source,
                expires_at,
            ),
        )
    return insight_id


def update_insight(insight_id: str, *, db_path: Path | None = None, **fields: Any) -> None:
    if not fields:
        return
    if "evidence" in fields and fields["evidence"] is not None and not isinstance(fields["evidence"], str):
        fields["evidence"] = json.dumps(fields["evidence"], ensure_ascii=False, default=str)
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with get_analytics_connection(db_path) as conn:
        conn.execute(
            f"UPDATE insights SET {assignments} WHERE id = ?",
            (*fields.values(), insight_id),
        )


def get_insight(insight_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with get_analytics_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()
    return _row_to_insight(row) if row else None


def list_insights(
    *,
    status: str | None = None,
    theme_id: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if theme_id:
        clauses.append("theme_id = ?")
        args.append(theme_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM insights {where}
            ORDER BY coalesce(published_at, created_at) DESC
            LIMIT ?
            """,
            (*args, limit),
        ).fetchall()
    return [_row_to_insight(r) for r in rows]


def add_feedback(
    insight_id: str,
    *,
    label: str,
    comment: str | None = None,
    user_id: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if label not in ("useful", "not_useful", "wrong"):
        raise ValueError(f"Invalid feedback label: {label!r}")
    feedback_id = uuid4().hex
    now = _utc_now()
    with get_analytics_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO insight_feedback (id, insight_id, label, comment, user_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feedback_id, insight_id, label, comment, user_id, now),
        )
    return {
        "id": feedback_id,
        "insight_id": insight_id,
        "label": label,
        "comment": comment,
        "user_id": user_id,
        "created_at": now,
    }


def list_feedback(insight_id: str | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    clause = "WHERE insight_id = ?" if insight_id else ""
    args = (insight_id,) if insight_id else ()
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM insight_feedback {clause} ORDER BY created_at DESC",
            args,
        ).fetchall()
    return [dict(r) for r in rows]


def feedback_stats(db_path: Path | None = None) -> dict[str, Any]:
    """useful / not_useful / wrong ratios — used to track Phase I success criteria."""
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT label, COUNT(*) AS n FROM insight_feedback GROUP BY label"
        ).fetchall()
    counts = {r["label"]: int(r["n"]) for r in rows}
    total = sum(counts.values())
    if total == 0:
        return {"total": 0, "useful_pct": 0.0, "not_useful_pct": 0.0, "wrong_pct": 0.0}
    return {
        "total": total,
        "useful_pct": round(100.0 * counts.get("useful", 0) / total, 1),
        "not_useful_pct": round(100.0 * counts.get("not_useful", 0) / total, 1),
        "wrong_pct": round(100.0 * counts.get("wrong", 0) / total, 1),
    }


def recent_published_map(
    *, window_days: int = 60, db_path: Path | None = None
) -> dict[tuple[str, str, str, str], str]:
    """Latest ``published_at`` per (metric_key, dim_name, dim_value, direction)
    within the lookback window — used for novelty dedupe (roadmap §8 scoring)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT metric_key, dim_name, dim_value, direction, MAX(published_at) AS last_pub
            FROM insights
            WHERE status = 'published' AND published_at >= ?
            GROUP BY metric_key, dim_name, dim_value, direction
            """,
            (cutoff,),
        ).fetchall()
    return {
        (r["metric_key"], r["dim_name"], r["dim_value"], r["direction"] or ""): r["last_pub"]
        for r in rows
    }


def insight_status_summary(db_path: Path | None = None) -> dict[str, Any]:
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM insights GROUP BY status"
        ).fetchall()
    return {r["status"]: int(r["n"]) for r in rows}
