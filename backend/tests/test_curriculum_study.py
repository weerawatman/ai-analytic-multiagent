"""curriculum_store + study_service tests (Phase K)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.app.services import curriculum_store, study_service


@pytest.fixture()
def curriculum_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        "backend.app.services.curriculum_store.get_local_dir",
        lambda settings=None: tmp_path,
    )
    monkeypatch.setattr(
        "backend.app.services.team_memory_store.get_local_dir",
        lambda settings=None: tmp_path,
    )
    (tmp_path / "knowledge" / "curriculum").mkdir(parents=True)
    (tmp_path / "team_memory").mkdir(parents=True)
    (tmp_path / "eval").mkdir(parents=True)
    return tmp_path


def test_seed_all_roles(curriculum_root: Path):
    docs = curriculum_store.ensure_all_curricula()
    assert set(docs.keys()) == set(curriculum_store.ROLES)
    da = curriculum_store.load_curriculum("data_analyst")
    assert da["stats"]["question_count"] >= 5
    assert da["stats"]["pass_rate_pct"] == 0.0


def test_pick_due_prefers_unattempted(curriculum_root: Path):
    curriculum_store.seed_curriculum("data_analyst")
    curriculum_store.record_attempt(
        "data_analyst",
        "da-001",
        answer_excerpt="ลองแล้ว",
        passed=False,
    )
    due = curriculum_store.pick_due_questions("data_analyst", n=2)
    ids = [q["id"] for q in due]
    assert "da-001" not in ids or due[0]["id"] != "da-001"
    assert due[0]["attempts"] == 0


def test_pass_rate_updates(curriculum_root: Path):
    curriculum_store.seed_curriculum("data_scientist")
    curriculum_store.record_attempt(
        "data_scientist",
        "ds-001",
        answer_excerpt="seasonality ชัด",
        passed=True,
        golden_match={"golden_question_id": "gq-x", "passed": True},
    )
    stats = curriculum_store.load_curriculum("data_scientist")["stats"]
    assert stats["attempted"] == 1
    assert stats["passed"] == 1
    assert stats["pass_rate_pct"] == 100.0


def test_study_session_with_mock_answer(curriculum_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "backend.app.services.eval_service.load_golden_questions",
        lambda active_only=True: [
            {
                "id": "gq-001",
                "expected_metric_key": "metric.revenue",
                "expected_keywords_th": ["ยอดขาย"],
                "active": True,
            }
        ],
    )

    async def fake_answer(q: dict) -> dict:
        return {
            "answer": "ยอดขายรวมไตรมาสล่าสุด 100 ล้าน",
            "sql_ok": True,
            "latency_s": 0.1,
        }

    result = asyncio.run(
        study_service.run_study_session(
            theme_id="sales",
            roles=["data_analyst"],
            questions_per_role=1,
            answer_fn=fake_answer,
        )
    )
    assert result["studied_count"] == 1
    assert result["studied"][0]["memory_status"] == "pending_ceo_approve"
    mem_path = curriculum_root / "team_memory" / "sales.json"
    assert mem_path.exists()


def test_approve_study_result(curriculum_root: Path):
    curriculum_store.append_study_result_to_memory(
        "sales",
        role="data_analyst",
        curriculum_question_id="da-001",
        question_th="ถาม",
        answer_excerpt="ตอบ",
    )
    from backend.app.services.team_memory_store import load_team_memory

    data = load_team_memory("sales")
    rid = data["study_results"][0]["id"]
    updated = curriculum_store.approve_study_result("sales", rid, approved=True)
    assert updated["study_results"][0]["status"] == "approved"
