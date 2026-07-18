"""sql_pattern_store tests (Phase J) — analytics.db CRUD + downvote filter."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services import snapshot_store, sql_pattern_store


@pytest.fixture()
def analytics_db(tmp_path: Path) -> Path:
    db = tmp_path / "analytics.db"
    snapshot_store.init_analytics_db(db)
    sql_pattern_store.init_pattern_tables(db)
    return db


def test_extract_table_refs():
    sql = "SELECT a FROM dbo.Sales s JOIN dbo.Customer c ON 1=1"
    refs = sql_pattern_store.extract_table_refs(sql)
    assert "dbo.Sales" in refs
    assert "dbo.Customer" in refs


def test_record_and_list_pattern(analytics_db: Path):
    pid = sql_pattern_store.record_pattern(
        theme_id="sales",
        question="ยอดขายเดือนนี้เท่าไหร่",
        sql="SELECT SUM(NetValue) FROM CE1SATG WHERE Period = '202409'",
        dialect="tsql",
        session_id="sess-1",
        message_id=42,
        db_path=analytics_db,
    )
    assert pid is not None
    rows = sql_pattern_store._list_candidates(
        dialect="tsql", theme_id="sales", limit=10, db_path=analytics_db
    )
    assert len(rows) == 1
    assert rows[0]["question"].startswith("ยอดขาย")
    assert rows[0]["session_id"] == "sess-1"


def test_record_pattern_rejects_empty(analytics_db: Path):
    assert sql_pattern_store.record_pattern(
        theme_id=None, question="  ", sql="SELECT 1", dialect="tsql", db_path=analytics_db
    ) is None
    assert sql_pattern_store.record_pattern(
        theme_id=None, question="q", sql="", dialect="tsql", db_path=analytics_db
    ) is None


def test_exclude_downvoted_by_session_message_and_job():
    candidates = [
        {"id": "1", "session_id": "s1", "message_id": 10, "job_id": None},
        {"id": "2", "session_id": "s2", "message_id": 20, "job_id": "job-bad"},
        {"id": "3", "session_id": "s3", "message_id": 30, "job_id": "job-ok"},
    ]
    downvoted = {("s1", 10, None), (None, None, "job-bad")}
    kept = sql_pattern_store._exclude_downvoted(candidates, downvoted)
    assert [c["id"] for c in kept] == ["3"]


def test_format_pattern_context_empty_and_nonempty():
    assert sql_pattern_store.format_pattern_context([]) == ""
    text = sql_pattern_store.format_pattern_context(
        [{"question": "Q1", "sql": "SELECT 1"}]
    )
    assert "Successful SQL patterns" in text
    assert "Q1" in text
    assert "SELECT 1" in text


@pytest.mark.asyncio
async def test_get_similar_patterns_filters_and_ranks(monkeypatch, analytics_db: Path):
    sql_pattern_store.record_pattern(
        theme_id="sales",
        question="revenue this month",
        sql="SELECT 1",
        dialect="postgres",
        session_id="keep",
        message_id=1,
        db_path=analytics_db,
    )
    sql_pattern_store.record_pattern(
        theme_id="sales",
        question="downvoted answer",
        sql="SELECT 2",
        dialect="postgres",
        session_id="bad",
        message_id=99,
        db_path=analytics_db,
    )
    # Wrong dialect should never appear
    sql_pattern_store.record_pattern(
        theme_id="sales",
        question="tsql only",
        sql="SELECT 3",
        dialect="tsql",
        db_path=analytics_db,
    )

    monkeypatch.setattr(
        "backend.app.services.chat_store.get_downvoted_refs",
        lambda: {("bad", 99, None)},
    )

    async def _passthrough(query, candidates, **kwargs):
        return candidates[: kwargs.get("k", 3)]

    monkeypatch.setattr(
        "backend.app.services.embedding_service.select_relevant", _passthrough
    )

    out = await sql_pattern_store.get_similar_patterns(
        "revenue", dialect="postgres", theme_id="sales", db_path=analytics_db
    )
    assert len(out) == 1
    assert out[0]["question"] == "revenue this month"


def test_inv7_module_has_no_app_db_literal():
    """Mirror conformance INV-7 for this file specifically."""
    source = Path(sql_pattern_store.__file__).read_text(encoding="utf-8")
    assert "app.db" not in source
