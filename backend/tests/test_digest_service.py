"""digest_service tests (Phase K)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.app.services import digest_service, insight_store, snapshot_store


@pytest.fixture()
def analytics_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "analytics.db"
    monkeypatch.setattr(
        "backend.app.services.snapshot_store.get_analytics_db_path",
        lambda settings=None: db,
    )
    monkeypatch.setattr(
        "backend.app.services.digest_service.get_local_dir",
        lambda settings=None: tmp_path,
    )
    snapshot_store.init_analytics_db(db)
    insight_store.init_insight_tables(db)
    (tmp_path / "briefings" / "digests").mkdir(parents=True, exist_ok=True)
    return db


def test_iso_week_key_format():
    key = digest_service.iso_week_key()
    assert len(key) == 7
    assert key[4] == "-"


def test_qoq_yoy_from_monthly_series(analytics_db: Path):
    rows = []
    # 15 months of revenue ending 202606
    periods = [
        "202504",
        "202505",
        "202506",
        "202507",
        "202508",
        "202509",
        "202510",
        "202511",
        "202512",
        "202601",
        "202602",
        "202603",
        "202604",
        "202605",
        "202606",
    ]
    for i, p in enumerate(periods):
        rows.append(
            {
                "metric_key": "metric.revenue",
                "period": p,
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 100.0 + i * 10,
                "source": "postgres",
            }
        )
    snapshot_store.upsert_snapshots(rows, db_path=analytics_db)
    qoy = digest_service.compute_qoq_yoy("metric.revenue", db_path=analytics_db)
    assert qoy["period_basis"] == digest_service.PERIOD_BASIS
    assert qoy["anchor_period"] == "202606"
    assert qoy["current_quarter"] is not None
    assert qoy["qoq_pct"] is not None
    assert qoy["yoy_pct"] is not None


def test_published_useful_filter(analytics_db: Path):
    iid = insight_store.create_insight(
        theme_id="sales",
        metric_key="metric.revenue",
        detector="anomaly",
        dim_name="__total__",
        dim_value="__total__",
        period="202606",
        direction="up",
        magnitude=1.0,
        significance=0.9,
        impact=0.5,
        novelty=0.5,
        score=0.8,
        rank_score=0.8,
        status="published",
        evidence={"value": 100},
        narrative_th="ยอดขึ้น",
        published_at="2026-07-01T00:00:00+00:00",
        source="postgres",
        db_path=analytics_db,
    )
    insight_store.add_feedback(iid, label="useful", db_path=analytics_db)
    useful = digest_service.list_published_useful_insights(db_path=analytics_db)
    assert len(useful) == 1
    assert useful[0]["id"] == iid

    insight_store.add_feedback(iid, label="wrong", db_path=analytics_db)
    assert digest_service.list_published_useful_insights(db_path=analytics_db) == []


def test_generate_digest_roundtrip(analytics_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(digest_service, "digests_dir", lambda: tmp_path / "briefings" / "digests")
    (tmp_path / "briefings" / "digests").mkdir(parents=True, exist_ok=True)

    snapshot_store.upsert_snapshots(
        [
            {
                "metric_key": "metric.revenue",
                "period": "202604",
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 10.0,
                "source": "offline",
            },
            {
                "metric_key": "metric.revenue",
                "period": "202605",
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 20.0,
                "source": "offline",
            },
            {
                "metric_key": "metric.revenue",
                "period": "202606",
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 30.0,
                "source": "offline",
            },
        ],
        db_path=analytics_db,
    )

    doc = asyncio.run(
        digest_service.generate_digest(week_key="2026-29", polish=False, db_path=analytics_db)
    )
    assert doc["week_key"] == "2026-29"
    assert doc["period_basis"] == digest_service.PERIOD_BASIS
    loaded = digest_service.load_digest("2026-29")
    assert loaded is not None
    assert loaded["week_key"] == "2026-29"
    listed = digest_service.list_digests()
    assert any(d["week_key"] == "2026-29" for d in listed)
