"""Phase D5 — PDCA persistent failure log."""

from __future__ import annotations

import asyncio
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


@pytest.mark.anyio
async def test_log_sql_failure_records_source(temp_storage):
    """Postgres-fallback auto-fallback (Phase E) — PDCA entries must say which
    connector produced the failing SQL, defaulting to 'fabric' when omitted."""
    await pdca_logger.log_sql_failure(
        theme_id="sales",
        user_prompt="ยอดขาย",
        sql="SELECT NETWR FROM VBRK",
        error="timeout",
        retry_count=1,
    )
    await pdca_logger.log_sql_failure(
        theme_id="sales",
        user_prompt="ยอดขาย",
        sql="SELECT netwr FROM vbrk LIMIT 5",
        error="connection refused",
        retry_count=2,
        source="postgres",
    )

    path = temp_storage / "logs" / "pdca_failures.jsonl"
    records = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert records[0]["source"] == "fabric"
    assert records[1]["source"] == "postgres"


@pytest.mark.anyio
async def test_concurrent_appends_produce_valid_jsonl(temp_storage):
    """Concurrent jobs append via threads — every line must stay valid JSON."""
    await asyncio.gather(
        *[
            pdca_logger.log_sql_failure(
                theme_id=f"theme-{i}",
                user_prompt="คำถาม " + "ก" * 200,
                sql=f"SELECT {i} FROM t",
                error="boom",
                retry_count=(i % 3) + 1,
            )
            for i in range(30)
        ]
    )

    path = temp_storage / "logs" / "pdca_failures.jsonl"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 30
    themes = {json.loads(ln)["theme_id"] for ln in lines}  # every line parses
    assert themes == {f"theme-{i}" for i in range(30)}
