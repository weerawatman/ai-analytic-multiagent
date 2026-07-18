"""SQLite snapshot store for metric time series (Phase H).

Lives in ``data/local/analytics/analytics.db`` (WAL) — never touches the chat
job database (INV-7). Pure persistence; no SQL against Fabric/Postgres here.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from backend.app.services.local_paths import get_analytics_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metric_snapshots (
    metric_key TEXT NOT NULL,
    period TEXT NOT NULL,
    dim_name TEXT NOT NULL,
    dim_value TEXT NOT NULL,
    value REAL,
    row_count INTEGER,
    source TEXT,
    refreshed_at TEXT NOT NULL,
    PRIMARY KEY (metric_key, period, dim_name, dim_value)
);

CREATE TABLE IF NOT EXISTS snapshot_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source TEXT,
    status TEXT NOT NULL,
    metrics_refreshed INTEGER DEFAULT 0,
    months_window TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_metric_period
    ON metric_snapshots(metric_key, period);
CREATE INDEX IF NOT EXISTS idx_snapshot_runs_started
    ON snapshot_runs(started_at DESC);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_analytics_db(db_path: Path | None = None) -> Path:
    path = db_path or get_analytics_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
    return path


@contextmanager
def get_analytics_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_analytics_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_snapshot_run(
    *,
    source: str,
    months_window: str,
    db_path: Path | None = None,
) -> str:
    run_id = uuid4().hex
    with get_analytics_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO snapshot_runs (id, started_at, source, status, months_window)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (run_id, _utc_now(), source, months_window),
        )
    return run_id


def finish_snapshot_run(
    run_id: str,
    *,
    status: str,
    metrics_refreshed: int = 0,
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    with get_analytics_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE snapshot_runs
            SET finished_at = ?, status = ?, metrics_refreshed = ?, error = ?
            WHERE id = ?
            """,
            (_utc_now(), status, metrics_refreshed, error, run_id),
        )


def upsert_snapshots(
    rows: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> int:
    """Upsert snapshot rows. Each dict needs metric_key, period, dim_name,
    dim_value, value, and optionally row_count, source, refreshed_at.
    """
    if not rows:
        return 0
    now = _utc_now()
    payload = [
        (
            r["metric_key"],
            r["period"],
            r["dim_name"],
            r["dim_value"],
            None if r.get("value") is None else float(r["value"]),
            int(r.get("row_count") or 0),
            r.get("source") or "",
            r.get("refreshed_at") or now,
        )
        for r in rows
    ]
    with get_analytics_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO metric_snapshots
                (metric_key, period, dim_name, dim_value, value, row_count, source, refreshed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric_key, period, dim_name, dim_value) DO UPDATE SET
                value = excluded.value,
                row_count = excluded.row_count,
                source = excluded.source,
                refreshed_at = excluded.refreshed_at
            """,
            payload,
        )
    return len(payload)


def get_series(
    metric_key: str,
    *,
    dim_name: str = "__total__",
    dim_value: str = "__total__",
    periods: list[str] | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT metric_key, period, dim_name, dim_value, value, row_count, source, refreshed_at
        FROM metric_snapshots
        WHERE metric_key = ? AND dim_name = ? AND dim_value = ?
    """
    params: list[Any] = [metric_key, dim_name, dim_value]
    if periods:
        placeholders = ",".join("?" for _ in periods)
        sql += f" AND period IN ({placeholders})"
        params.extend(periods)
    sql += " ORDER BY period ASC"
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_period_slice(
    metric_key: str,
    period: str,
    *,
    dim_name: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """All dim values for one metric × period × dimension (excludes __total__)."""
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT metric_key, period, dim_name, dim_value, value, row_count, source, refreshed_at
            FROM metric_snapshots
            WHERE metric_key = ? AND period = ? AND dim_name = ?
              AND dim_value != '__total__'
            ORDER BY value DESC
            """,
            (metric_key, period, dim_name),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_run(db_path: Path | None = None) -> dict[str, Any] | None:
    with get_analytics_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM snapshot_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def list_runs(limit: int = 20, db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM snapshot_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def snapshot_status(db_path: Path | None = None) -> dict[str, Any]:
    with get_analytics_connection(db_path) as conn:
        n_rows = conn.execute("SELECT COUNT(*) FROM metric_snapshots").fetchone()[0]
        n_metrics = conn.execute(
            "SELECT COUNT(DISTINCT metric_key) FROM metric_snapshots"
        ).fetchone()[0]
        n_periods = conn.execute(
            "SELECT COUNT(DISTINCT period) FROM metric_snapshots"
        ).fetchone()[0]
    run = latest_run(db_path)
    return {
        "row_count": int(n_rows),
        "metric_count": int(n_metrics),
        "period_count": int(n_periods),
        "latest_run": run,
        "db_path": str(db_path or get_analytics_db_path()),
    }
