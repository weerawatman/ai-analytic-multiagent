"""Insight pipeline tests (Phase I) — offline / mocked LLM & registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services import insight_pipeline, insight_store, snapshot_store


@pytest.fixture()
def analytics_db(tmp_path: Path) -> Path:
    db = tmp_path / "analytics.db"
    snapshot_store.init_analytics_db(db)
    insight_store.init_insight_tables(db)
    return db


# ---------------------------------------------------------------------------
# validate_narrative_numbers (INV-4)
# ---------------------------------------------------------------------------


def test_validate_accepts_numbers_present_in_evidence():
    evidence = {"metric_key": "metric.revenue", "value": 1234.5, "baseline": 1000.0, "delta": 234.5}
    narrative = "ยอดขายเดือนนี้ 1,234.50 เพิ่มขึ้นจากฐาน 1000.0 คิดเป็น 234.5"
    assert insight_pipeline.validate_narrative_numbers(narrative, evidence)


def test_validate_rejects_hallucinated_number():
    evidence = {"metric_key": "metric.revenue", "value": 1234.5}
    narrative = "ยอดขายเดือนนี้ 9,999,999 บาท"
    assert not insight_pipeline.validate_narrative_numbers(narrative, evidence)


def test_validate_allows_small_ordinal_counts():
    evidence = {"value": 500.0}
    narrative = "อันดับ 1 ในช่วง 3 เดือนที่ผ่านมามีมูลค่า 500.0"
    assert insight_pipeline.validate_narrative_numbers(narrative, evidence)


# ---------------------------------------------------------------------------
# Narration + fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_narrate_falls_back_when_llm_unavailable(monkeypatch):
    def _boom(**_kwargs):
        raise RuntimeError("no ollama")

    monkeypatch.setattr(insight_pipeline, "make_chat_ollama", _boom)
    candidate = {
        "metric_key": "metric.revenue",
        "detector": "anomaly",
        "period": "202409",
        "direction": "down",
        "magnitude": 500.0,
        "evidence": {"period": "202409", "value": 100.0, "baseline": 600.0, "delta": -500.0},
    }
    text = await insight_pipeline._narrate_with_validation(candidate)
    assert "metric.revenue" in text
    assert insight_pipeline.validate_narrative_numbers(text, candidate["evidence"])


@pytest.mark.asyncio
async def test_narrate_retries_then_falls_back_on_hallucination(monkeypatch):
    calls = {"n": 0}

    class _FakeResponse:
        content = "ยอดขายพุ่งขึ้น 9,999,999 บาท อย่างเหลือเชื่อ"

    class _FakeLLM:
        async def ainvoke(self, prompt):
            calls["n"] += 1
            return _FakeResponse()

    monkeypatch.setattr(insight_pipeline, "make_chat_ollama", lambda **kw: _FakeLLM())
    candidate = {
        "metric_key": "metric.revenue",
        "detector": "anomaly",
        "period": "202409",
        "direction": "up",
        "magnitude": 500.0,
        "evidence": {"period": "202409", "value": 600.0, "baseline": 100.0, "delta": 500.0},
    }
    text = await insight_pipeline._narrate_with_validation(candidate)
    assert calls["n"] == 2  # first attempt + one retry, both hallucinated
    assert insight_pipeline.validate_narrative_numbers(text, candidate["evidence"])
    assert "metric.revenue" in text  # fell back to the deterministic template


@pytest.mark.asyncio
async def test_narrate_accepts_valid_llm_output(monkeypatch):
    class _FakeResponse:
        content = "ยอดขายเดือน 202409 เพิ่มขึ้นจาก 100.0 เป็น 600.0 (เพิ่ม 500.0) ควรตรวจสอบสาเหตุ?"

    class _FakeLLM:
        async def ainvoke(self, prompt):
            return _FakeResponse()

    monkeypatch.setattr(insight_pipeline, "make_chat_ollama", lambda **kw: _FakeLLM())
    candidate = {
        "metric_key": "metric.revenue",
        "detector": "anomaly",
        "period": "202409",
        "direction": "up",
        "magnitude": 500.0,
        "evidence": {"period": "202409", "value": 600.0, "baseline": 100.0, "delta": 500.0},
    }
    text = await insight_pipeline._narrate_with_validation(candidate)
    assert text == _FakeResponse.content


# ---------------------------------------------------------------------------
# Candidate building / scoring
# ---------------------------------------------------------------------------


def test_candidates_for_metric_flags_recent_crash(analytics_db: Path):
    rows = []
    for m in range(1, 13):
        period = f"2024{m:02d}"
        value = 100.0 if m != 12 else 10.0
        rows.append(
            {
                "metric_key": "metric.revenue",
                "period": period,
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": value,
                "source": "postgres",
            }
        )
    snapshot_store.upsert_snapshots(rows, db_path=analytics_db)
    candidates = insight_pipeline._candidates_for_metric(
        "metric.revenue", theme_id="sales", db_path=analytics_db
    )
    assert any(c["period"] == "202412" and c["direction"] == "down" for c in candidates)
    for c in candidates:
        assert c["evidence"]["source"] == "postgres"


def test_score_candidates_orders_by_rank_score(analytics_db: Path):
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
    assert scored[0]["status"] == "scored"
    assert scored[0]["rank_score"] > scored[1]["rank_score"]


def test_novelty_dedupe_suppresses_recent_duplicate(analytics_db: Path):
    insight_store.create_insight(
        theme_id="sales",
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
        status="published",
        evidence={"value": 1.0},
        published_at=insight_pipeline._utc_now(),
        db_path=analytics_db,
    )
    candidates = [
        {
            "metric_key": "metric.a",
            "dim_name": "__total__",
            "dim_value": "__total__",
            "direction": "up",
            "raw_significance": 0.9,
            "impact": 0.9,
        }
    ]
    scored = insight_pipeline._score_candidates(candidates, db_path=analytics_db)
    assert scored[0]["status"] == "suppressed"
    assert scored[0]["novelty"] < 0.05


# ---------------------------------------------------------------------------
# Full pipeline (mocked LLM + registry + refresh)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_insight_pipeline_end_to_end(analytics_db: Path, monkeypatch):
    rows = []
    for m in range(1, 13):
        period = f"2024{m:02d}"
        value = 100.0 if m != 12 else 10.0
        rows.append(
            {
                "metric_key": "metric.revenue",
                "period": period,
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": value,
                "source": "postgres",
            }
        )
    snapshot_store.upsert_snapshots(rows, db_path=analytics_db)

    async def _fake_list_metrics(**_kwargs):
        return [
            {
                "metric_key": "metric.revenue",
                "expression": "Revenue",
                "derived": None,
                "status": "approved",
            }
        ]

    async def _fake_refresh(*, mode="auto", db_path=None):
        return {"status": "skipped", "reason": "test"}

    class _FakeLLM:
        async def ainvoke(self, prompt):
            class R:
                content = "สรุปสถานการณ์จากข้อมูลจริง"

            return R()

    monkeypatch.setattr(insight_pipeline, "list_metrics", _fake_list_metrics)
    monkeypatch.setattr(insight_pipeline, "refresh_snapshots", _fake_refresh)
    monkeypatch.setattr(insight_pipeline, "make_chat_ollama", lambda **kw: _FakeLLM())

    steps: list[str] = []
    result = await insight_pipeline.run_insight_pipeline(
        theme_id="sales", top_k=5, step_cb=steps.append, db_path=analytics_db
    )
    assert steps == [
        "refresh_snapshots",
        "run_detectors",
        "score_candidates",
        "narrate_top",
        "publish",
    ]
    assert result["candidates_total"] >= 1
    assert result["published"] >= 1

    published = insight_store.list_insights(status="published", db_path=analytics_db)
    assert len(published) == result["published"]
    for insight in published:
        assert insight_pipeline.validate_narrative_numbers(
            insight["narrative_th"], insight["evidence"]
        )


def test_inv4_smoke_validator_is_called_in_module():
    from pathlib import Path as P

    text = (
        P(__file__).resolve().parents[1] / "app" / "services" / "insight_pipeline.py"
    ).read_text(encoding="utf-8")
    assert "validate_narrative_numbers" in text
