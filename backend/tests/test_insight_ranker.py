"""insight_ranker tests (Phase J) — heuristic default, ML gate, INV-8 constants."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services import insight_ranker, insight_store, snapshot_store


@pytest.fixture()
def analytics_db(tmp_path: Path) -> Path:
    db = tmp_path / "analytics.db"
    snapshot_store.init_analytics_db(db)
    insight_store.init_insight_tables(db)
    return db


def test_inv8_constants_frozen():
    assert insight_ranker.MIN_LABELS_FOR_ML == 100
    assert insight_ranker.MIN_AUC_GATE == 0.6


def test_heuristic_score_matches_pipeline_formula():
    insight = {"raw_significance": 0.8, "impact": 0.5, "novelty": 1.0}
    assert insight_ranker.heuristic_score(insight) == pytest.approx(0.4)


def test_apply_ranker_noop_when_ml_dormant(tmp_path: Path):
    candidates = [
        {"metric_key": "a", "rank_score": 0.9, "significance": 0.9, "impact": 1.0},
        {"metric_key": "b", "rank_score": 0.1, "significance": 0.1, "impact": 1.0},
    ]
    out = insight_ranker.apply_ranker(candidates, model_path=tmp_path / "missing.pkl")
    assert out is candidates
    assert out[0]["rank_score"] == 0.9


def test_score_insights_falls_back_to_heuristic(tmp_path: Path):
    insights = [
        {"metric_key": "low", "significance": 0.1, "impact": 0.1, "novelty": 1.0},
        {"metric_key": "high", "significance": 0.9, "impact": 0.9, "novelty": 1.0},
    ]
    ranked = insight_ranker.score_insights(insights, model_path=tmp_path / "missing.pkl")
    assert ranked[0]["metric_key"] == "high"
    assert ranked[0]["rank_score"] > ranked[1]["rank_score"]


def test_train_ranker_insufficient_labels(analytics_db: Path, tmp_path: Path, monkeypatch):
    events = tmp_path / "ranker_events.jsonl"
    monkeypatch.setattr(insight_ranker, "_events_path", lambda: events)

    result = insight_ranker.train_ranker(
        db_path=analytics_db, model_path=tmp_path / "model.pkl"
    )
    assert result["status"] == "insufficient_labels"
    assert result["n_labels"] == 0
    assert events.exists()
    assert "insufficient_labels" in events.read_text(encoding="utf-8")
    assert not insight_ranker.is_ml_active(model_path=tmp_path / "model.pkl")


def _seed_separable_labels(db: Path, n_each: int = 60) -> None:
    """Useful = high significance/impact; not_useful = low — AUC should clear 0.6."""
    for i in range(n_each):
        useful_id = insight_store.create_insight(
            theme_id="sales",
            metric_key=f"metric.u{i}",
            detector="anomaly",
            dim_name="__total__",
            dim_value="__total__",
            period="202409",
            direction="up",
            magnitude=1.0,
            significance=0.9,
            impact=0.9,
            novelty=1.0,
            score=0.81,
            rank_score=0.81,
            status="published",
            evidence={"value": 1.0},
            db_path=db,
        )
        insight_store.add_feedback(useful_id, label="useful", db_path=db)

        junk_id = insight_store.create_insight(
            theme_id="sales",
            metric_key=f"metric.j{i}",
            detector="trend",
            dim_name="__total__",
            dim_value="__total__",
            period="202409",
            direction="down",
            magnitude=0.1,
            significance=0.05,
            impact=0.05,
            novelty=1.0,
            score=0.0025,
            rank_score=0.0025,
            status="published",
            evidence={"value": 0.1},
            db_path=db,
        )
        insight_store.add_feedback(junk_id, label="not_useful", db_path=db)


def test_train_ranker_promotes_when_auc_clears_gate(
    analytics_db: Path, tmp_path: Path, monkeypatch
):
    events = tmp_path / "ranker_events.jsonl"
    monkeypatch.setattr(insight_ranker, "_events_path", lambda: events)
    model_path = tmp_path / "insight_ranker.pkl"

    _seed_separable_labels(analytics_db, n_each=60)  # 120 labels >= 100
    result = insight_ranker.train_ranker(
        db_path=analytics_db, model_path=model_path, min_labels=100, min_auc=0.6
    )
    assert result["status"] == "promoted"
    assert result["auc"] >= 0.6
    assert model_path.exists()
    assert insight_ranker.is_ml_active(model_path=model_path)

    candidates = [
        {
            "detector": "anomaly",
            "significance": 0.95,
            "impact": 0.95,
            "novelty": 1.0,
            "rank_score": 0.5,
        },
        {
            "detector": "trend",
            "significance": 0.02,
            "impact": 0.02,
            "novelty": 1.0,
            "rank_score": 0.5,
        },
    ]
    ranked = insight_ranker.apply_ranker(candidates, model_path=model_path)
    assert ranked[0]["rank_score"] != 0.5 or ranked[1]["rank_score"] != 0.5
    assert "promoted" in events.read_text(encoding="utf-8")


def test_train_ranker_keeps_heuristic_when_auc_fails(
    analytics_db: Path, tmp_path: Path, monkeypatch
):
    events = tmp_path / "ranker_events.jsonl"
    monkeypatch.setattr(insight_ranker, "_events_path", lambda: events)
    model_path = tmp_path / "insight_ranker.pkl"

    # Random-ish labels: same features for both classes → AUC ~0.5
    for i in range(55):
        iid = insight_store.create_insight(
            theme_id="sales",
            metric_key=f"metric.r{i}",
            detector="anomaly",
            dim_name="__total__",
            dim_value="__total__",
            period="202409",
            direction="up",
            magnitude=1.0,
            significance=0.5,
            impact=0.5,
            novelty=1.0,
            score=0.25,
            rank_score=0.25,
            status="published",
            evidence={"value": 1.0},
            db_path=analytics_db,
        )
        insight_store.add_feedback(
            iid, label="useful" if i % 2 == 0 else "not_useful", db_path=analytics_db
        )

    result = insight_ranker.train_ranker(
        db_path=analytics_db,
        model_path=model_path,
        min_labels=50,
        min_auc=0.99,  # impossible gate → must keep heuristic
    )
    assert result["status"] == "kept_heuristic"
    assert not model_path.exists()
    assert not insight_ranker.is_ml_active(model_path=model_path)
    assert "kept_heuristic" in events.read_text(encoding="utf-8")


def test_pipeline_score_candidates_unchanged_with_dormant_ml(analytics_db: Path, tmp_path: Path):
    """Wiring smoke: insight_pipeline._score_candidates still orders by heuristic."""
    from backend.app.services import insight_pipeline

    candidates = [
        {
            "metric_key": "metric.a",
            "dim_name": "__total__",
            "dim_value": "__total__",
            "direction": "up",
            "raw_significance": 0.9,
            "impact": 0.9,
        },
        {
            "metric_key": "metric.b",
            "dim_name": "__total__",
            "dim_value": "__total__",
            "direction": "down",
            "raw_significance": 0.1,
            "impact": 0.1,
        },
    ]
    scored = insight_pipeline._score_candidates(candidates, db_path=analytics_db)
    assert scored[0]["metric_key"] == "metric.a"
    assert scored[0]["rank_score"] > scored[1]["rank_score"]
