"""Phase D5 — PDCA persistent failure log."""

from __future__ import annotations

import json

import pytest

from backend.app.services import pdca_logger


@pytest.mark.anyio
async def test_log_sql_failure_appends_every_attempt(temp_storage):
    await pdca_logger.log_sql_failure(
        theme_id="sales",
        user_prompt="ยอดขายทั้งหมด",
        sql="SELECT * FROM VBRK",
        error="row count exceeded",
        retry_count=1,
    )
    await pdca_logger.log_sql_failure(
        theme_id="sales",
        user_prompt="ยอดขายทั้งหมด",
        sql="SELECT * FROM VBRK WHERE GJAHR='2024'",
        error="invalid column",
        retry_count=2,
    )
    await pdca_logger.log_sql_failure(
        theme_id="sales",
        user_prompt="ยอดขายทั้งหมด",
        sql="SELECT NETWR FROM VBRK WHERE GJAHR='2024'",
        error="timeout",
        retry_count=3,
    )

    path = temp_storage / "logs" / "pdca_failures.jsonl"
    assert path.exists()
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 3

    records = [json.loads(ln) for ln in lines]
    for i, rec in enumerate(records, start=1):
        assert rec["kind"] == "sql"
        assert rec["theme_id"] == "sales"
        assert rec["user_prompt"] == "ยอดขายทั้งหมด"
        assert "sql" in rec and rec["sql"]
        assert "error" in rec and rec["error"]
        assert rec["retry_count"] == i
        assert rec.get("timestamp") or rec.get("at")
