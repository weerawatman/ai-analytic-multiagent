"""Insight store tests (Phase I) — offline SQLite CRUD."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.services import insight_store, snapshot_store


@pytest.fixture()
def analytics_db(tmp_path: Path) -> Path:
    db = tmp_path / "analytics.db"
    snapshot_store.init_analytics_db(db)
    insight_store.init_insight_tables(db)
    return db


def _base_kwargs(**overrides):
    kwargs = dict(
        theme_id=None,
        metric_key="metric.a",
        detector="anomaly",
        dim_name="__total__",
        dim_value="__total__",
        period="202409",
        direction="up",
        magnitude=1.0,
        significance=1.0,
        impact=1.0,
        novelty=1.0,
        score=1.0,
        rank_score=1.0,
        status="scored",
        evidence={"value": 1.0},
    )
    kwargs.update(overrides)
    return kwargs


def test_create_get_list_insight(analytics_db: Path):
    insight_id = insight_store.create_insight(
        **_base_kwargs(
            theme_id="sales",
            metric_key="metric.revenue",
            direction="down",
            status="published",
            evidence={"value": 100.0, "baseline": 600.0},
            published_at="2026-07-18T00:00:00+00:00",
            narrative_th="ยอดขายลดลง 500.0",
        ),
        db_path=analytics_db,
    )
    got = insight_store.get_insight(insight_id, db_path=analytics_db)
    assert got is not None
    assert got["metric_key"] == "metric.revenue"
    assert got["evidence"] == {"value": 100.0, "baseline": 600.0}

    listed = insight_store.list_insights(status="published", db_path=analytics_db)
    assert len(listed) == 1
    assert listed[0]["id"] == insight_id

    empty = insight_store.list_insights(status="scored", db_path=analytics_db)
    assert empty == []


def test_update_insight(analytics_db: Path):
    insight_id = insight_store.create_insight(**_base_kwargs(), db_path=analytics_db)
    insight_store.update_insight(
        insight_id, status="published", narrative_th="test", db_path=analytics_db
    )
    got = insight_store.get_insight(insight_id, db_path=analytics_db)
    assert got["status"] == "published"
    assert got["narrative_th"] == "test"


def test_feedback_lifecycle(analytics_db: Path):
    insight_id = insight_store.create_insight(
        **_base_kwargs(status="published"), db_path=analytics_db
    )
    insight_store.add_feedback(insight_id, label="useful", db_path=analytics_db)
    insight_store.add_feedback(insight_id, label="wrong", comment="ผิด", db_path=analytics_db)

    with pytest.raises(ValueError):
        insight_store.add_feedback(insight_id, label="nope", db_path=analytics_db)

    items = insight_store.list_feedback(insight_id, db_path=analytics_db)
    assert len(items) == 2

    stats = insight_store.feedback_stats(db_path=analytics_db)
    assert stats["total"] == 2
    assert stats["useful_pct"] == 50.0
    assert stats["wrong_pct"] == 50.0


def test_recent_published_map_window(analytics_db: Path):
    old_time = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    recent_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    insight_store.create_insight(
        **_base_kwargs(
            metric_key="metric.old", direction="up", status="published", published_at=old_time
        ),
        db_path=analytics_db,
    )
    insight_store.create_insight(
        **_base_kwargs(
            metric_key="metric.recent",
            direction="down",
            status="published",
            published_at=recent_time,
        ),
        db_path=analytics_db,
    )
    recent_map = insight_store.recent_published_map(window_days=60, db_path=analytics_db)
    assert ("metric.recent", "__total__", "__total__", "down") in recent_map
    assert ("metric.old", "__total__", "__total__", "up") not in recent_map


def test_insight_status_summary(analytics_db: Path):
    insight_store.create_insight(
        **_base_kwargs(metric_key="metric.a", status="scored"), db_path=analytics_db
    )
    insight_store.create_insight(
        **_base_kwargs(metric_key="metric.b", direction="down", status="suppressed"),
        db_path=analytics_db,
    )
    summary = insight_store.insight_status_summary(db_path=analytics_db)
    assert summary == {"scored": 1, "suppressed": 1}


def test_inv7_no_app_db_string():
    root = Path(__file__).resolve().parents[1] / "app" / "services"
    banned = "app." + "db"
    text = (root / "insight_store.py").read_text(encoding="utf-8")
    assert banned not in text
