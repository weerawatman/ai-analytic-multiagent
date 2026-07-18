"""knowledge aggregation + eval trend (Phase K)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services import eval_service, knowledge_store, lesson_miner


@pytest.fixture()
def knowledge_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        "backend.app.services.knowledge_store.get_local_dir",
        lambda settings=None: tmp_path,
    )
    monkeypatch.setattr(
        "backend.app.services.lesson_miner.get_local_dir",
        lambda settings=None: tmp_path,
    )
    (tmp_path / "knowledge").mkdir(parents=True)
    (tmp_path / "eval" / "results").mkdir(parents=True)
    return tmp_path


def test_aggregate_theme_overrides_global(knowledge_root: Path):
    gloss = {
        "version": "1.0",
        "items": [
            {
                "id": "1",
                "field_key": "metric.revenue",
                "definition_th": "global def",
                "status": "approved",
            },
            {
                "id": "2",
                "field_key": "metric.revenue",
                "definition_th": "sales override",
                "theme": "sales",
                "status": "approved",
            },
            {
                "id": "3",
                "field_key": "metric.cost",
                "definition_th": "draft hide",
                "status": "draft",
            },
        ],
    }
    (knowledge_root / "knowledge" / "glossary.json").write_text(
        json.dumps(gloss, ensure_ascii=False), encoding="utf-8"
    )
    (knowledge_root / "knowledge" / "targets.json").write_text(
        '{"version":"1.0","items":[]}', encoding="utf-8"
    )
    (knowledge_root / "knowledge" / "relationships.json").write_text(
        '{"version":"1.0","items":[]}', encoding="utf-8"
    )
    lesson_miner.write_lessons(
        [
            {
                "error_class": "timeout",
                "count": 2,
                "lesson_th": "ลด timeout",
                "example_error": "HYT00",
                "last_seen": "t",
            }
        ],
        path=knowledge_root / "knowledge" / "sql_lessons.json",
    )

    agg = knowledge_store.aggregate_approved_knowledge(theme="sales")
    assert agg["counts"]["glossary"] == 1
    assert agg["glossary"][0]["definition_th"] == "sales override"
    assert agg["glossary"][0]["layer"] == "theme_override"
    assert agg["counts"]["lessons"] == 1


def test_eval_trend_lists_runs(knowledge_root: Path, monkeypatch: pytest.MonkeyPatch):
    results = knowledge_root / "eval" / "results"
    monkeypatch.setattr(eval_service, "results_dir", lambda: results)
    for i, acc in enumerate((10.0, 25.0, 40.0)):
        run_id = f"run{i}"
        (results / f"{run_id}.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "started_at": f"2026-07-0{i+1}T00:00:00+00:00",
                    "finished_at": f"2026-07-0{i+1}T01:00:00+00:00",
                    "question_count": 10,
                    "passed": int(acc / 10),
                    "accuracy_pct": acc,
                    "sql_success_rate": acc,
                    "median_latency_s": 1.0,
                    "harness_baseline": False,
                }
            ),
            encoding="utf-8",
        )
    trend = eval_service.eval_trend()
    assert trend["run_count"] == 3
    assert trend["first_accuracy_pct"] == 10.0
    assert trend["latest_accuracy_pct"] == 40.0
