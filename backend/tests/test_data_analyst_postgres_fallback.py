"""Data Analyst dialect-aware SQL generation for the Postgres auto-fallback.

Fabric is always preferred; when it is unreachable/paused and the Postgres
WH_Silver mirror is configured, DA must write PostgreSQL (not T-SQL) SQL —
the two dialects are not interchangeable (TOP vs LIMIT, GETDATE() vs NOW()).
The active source is decided *before* the LLM writes SQL.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from backend.app.agents import data_analyst
from backend.app.agents.data_analyst import _classify_sql_error, data_analyst_node
from backend.app.agents.state import AgentState


@pytest.mark.anyio
async def test_data_analyst_writes_postgres_dialect_when_fabric_down(temp_storage, monkeypatch):
    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: False)
    monkeypatch.setattr(data_analyst, "pg_can_query", lambda: True)
    monkeypatch.setattr(data_analyst, "read_trusted_layer", AsyncMock(return_value={"metrics": []}))

    captured = {}

    class FakeLLM:
        async def ainvoke(self, messages):
            captured["system_prompt"] = messages[0]["content"]
            return SimpleNamespace(
                content=(
                    "ANALYSIS: draft\nSQL:\n```sql\nSELECT netwr FROM vbrk LIMIT 5\n```\n"
                    "ASSUMPTIONS:\n- grain daily"
                )
            )

    monkeypatch.setattr(data_analyst, "llm", FakeLLM())

    exec_calls = {}

    async def fake_enforce(sql, source, settings=None):
        exec_calls["guard_source"] = source
        return 5

    async def fake_run_sql(sql, *, mode="explore", max_rows=None, source="fabric"):
        exec_calls["run_source"] = source
        return {"rows": [{"netwr": 100}], "columns": ["netwr"], "source": source}

    monkeypatch.setattr(data_analyst, "enforce_row_count_threshold_for_source_async", fake_enforce)
    monkeypatch.setattr(data_analyst, "run_sql_async", fake_run_sql)

    state = AgentState(
        thread_id="t-pg",
        mode="explore",
        theme="sales",
        theme_id="sales",
        discovery_context="## VBRK\n  - NETWR (decimal)",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    result = await data_analyst_node(state)

    assert "PostgreSQL" in captured["system_prompt"]
    assert exec_calls["guard_source"] == "postgres"
    assert exec_calls["run_source"] == "postgres"
    assert result["sql_source"] == "postgres"
    assert result["sql_error"] == ""


@pytest.mark.anyio
async def test_data_analyst_offline_when_fabric_and_postgres_both_down(temp_storage, monkeypatch):
    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: False)
    monkeypatch.setattr(data_analyst, "pg_can_query", lambda: False)
    monkeypatch.setattr(data_analyst, "read_trusted_layer", AsyncMock(return_value={"metrics": []}))

    async def boom(*a, **k):
        raise AssertionError("no SQL should run when both sources are offline")

    monkeypatch.setattr(data_analyst, "run_sql_async", boom)

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(
                content="ANALYSIS: draft\nSQL:\n```sql\nSELECT 1\n```\nASSUMPTIONS:\n- none"
            )

    monkeypatch.setattr(data_analyst, "llm", FakeLLM())

    state = AgentState(
        thread_id="t-offline",
        mode="explore",
        theme="sales",
        theme_id="sales",
        discovery_context="## VBRK\n  - NETWR (decimal)",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    result = await data_analyst_node(state)
    assert "SQL_SKIPPED" in result["query_result"]


@pytest.mark.anyio
async def test_retry_switches_to_postgres_dialect_after_fabric_drops(temp_storage, monkeypatch):
    """A failed attempt was written in T-SQL against Fabric; by the time the
    retry runs, Fabric just got marked unreachable — the retry must be told
    to rewrite in PostgreSQL, not resend the same T-SQL."""
    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: False)
    monkeypatch.setattr(data_analyst, "pg_can_query", lambda: True)
    monkeypatch.setattr(data_analyst, "log_sql_failure", AsyncMock())

    captured = {}

    class FixItLLM:
        async def ainvoke(self, prompt):
            captured["retry_prompt"] = prompt
            return SimpleNamespace(content="```sql\nSELECT netwr FROM vbrk LIMIT 5\n```")

    monkeypatch.setattr(data_analyst, "llm", FixItLLM())

    async def fake_enforce(sql, source, settings=None):
        return 5

    async def fake_run_sql(sql, *, mode="explore", max_rows=None, source="fabric"):
        return {"rows": [{"netwr": 100}], "columns": ["netwr"], "source": source}

    monkeypatch.setattr(data_analyst, "enforce_row_count_threshold_for_source_async", fake_enforce)
    monkeypatch.setattr(data_analyst, "run_sql_async", fake_run_sql)

    state = AgentState(
        thread_id="t-retry-pg",
        mode="explore",
        discovery_context="## VBRK\n  - NETWR",
        generated_sql="SELECT TOP 5 NETWR FROM VBRK ORDER BY NETWR DESC",
        query_result="ANALYSIS: draft\nSQL_ATTEMPT_FAILED: การรัน SQL เกินเวลาที่กำหนด",
        sql_error="timeout: query exceeded 300s",
        sql_source="fabric",
        sql_retry_count=1,
        messages=[HumanMessage(content="ยอดขาย")],
    )
    result = await data_analyst_node(state)

    assert "PostgreSQL" in captured["retry_prompt"]
    assert result["sql_source"] == "postgres"
    assert result["sql_error"] == ""
    assert result["generated_sql"] == "SELECT netwr FROM vbrk LIMIT 5"


@pytest.mark.parametrize(
    "error_text,expected_class",
    [
        ('column "badcol" does not exist', "invalid_column"),
        ("ERROR: 42703: column vbrk.badcol does not exist", "invalid_column"),
        ("psycopg2.OperationalError: could not connect to server", "connection"),
        ("FATAL: connection to server failed (08006)", "connection"),
        ("canceling statement due to statement timeout (57014)", "timeout"),
    ],
)
def test_classify_sql_error_recognizes_postgres_patterns(error_text, expected_class):
    assert _classify_sql_error(error_text) == expected_class
