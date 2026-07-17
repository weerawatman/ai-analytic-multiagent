"""Phase D2/D3 — SQL retry loop-back + graceful degradation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from backend.app.agents.data_analyst import (
    MAX_SQL_ATTEMPTS,
    SQL_FAILED_SUMMARY_TH,
    _classify_sql_error,
    _fail_sql_attempt,
    _retry_guidance,
    data_analyst_node,
)
from backend.app.agents.orchestrator import after_analyst
from backend.app.agents.state import AgentState
from backend.app.services.fabric_sql import RowCountExceeded
from backend.app.services.quality_assembly import (
    SQL_FAILED_CEO_MSG_TH,
    build_quality_payload,
    format_explore_response_th,
)


def test_after_analyst_loops_while_retries_remain():
    state = AgentState(
        sql_error="ชื่อคอลัมน์ผิด",
        sql_failed=False,
        sql_retry_count=1,
        mode="explore",
        use_collaborative_flow=True,
    )
    assert after_analyst(state) == "retry_sql"


def test_after_analyst_stops_when_sql_failed():
    state = AgentState(
        sql_error="still broken",
        sql_failed=True,
        sql_retry_count=MAX_SQL_ATTEMPTS,
        mode="explore",
        use_collaborative_flow=True,
    )
    assert after_analyst(state) == "explore_critique"


def test_after_analyst_trusted_path_without_error():
    state = AgentState(mode="trusted", use_collaborative_flow=False, sql_error="")
    assert after_analyst(state) == "summarize"


def test_error_classes_have_retry_guidance():
    assert _classify_sql_error(RowCountExceeded(99999, 50000)) == "row_count"
    assert _classify_sql_error("Invalid column name 'FOO'. (42S22)") == "invalid_column"
    assert _classify_sql_error(RuntimeError("syntax near")) == "generic"
    for klass in ("row_count", "invalid_column", "generic"):
        text = _retry_guidance(klass, "detail")
        assert "Error detail" in text
        assert len(text) > 20


@pytest.mark.anyio
async def test_loop_back_exactly_three_attempts(temp_storage, monkeypatch):
    """Graph-level loop: data_analyst runs at most 3 times then sql_failed=True."""
    calls = {"n": 0}

    async def always_fail(state: AgentState) -> dict:
        calls["n"] += 1
        new_count = state.sql_retry_count + 1
        friendly = f"รัน SQL ไม่สำเร็จ (SyntheticError: boom-{new_count})"
        sql_failed = new_count >= MAX_SQL_ATTEMPTS
        content = f"SQL_ATTEMPT_FAILED: {friendly}"
        if sql_failed:
            content += f"\n\n{SQL_FAILED_SUMMARY_TH}"
        return {
            "messages": [AIMessage(content=content, name="data_analyst")],
            "current_agent": "data_analyst",
            "generated_sql": "SELECT badcol FROM t",
            "query_result": content,
            "sql_retry_count": new_count,
            "sql_error": friendly,
            "sql_failed": sql_failed,
            "step_errors": [f"data_analyst SQL: {friendly}"],
        }

    builder = StateGraph(AgentState)
    builder.add_node("data_analyst", always_fail)
    builder.add_node("done", lambda state: {"final_answer": state.query_result})
    builder.set_entry_point("data_analyst")
    builder.add_conditional_edges(
        "data_analyst",
        after_analyst,
        {"retry_sql": "data_analyst", "explore_critique": "done", "summarize": "done"},
    )
    builder.add_edge("done", END)
    graph = builder.compile()

    result = await graph.ainvoke(
        AgentState(
            messages=[HumanMessage(content="ยอดขาย")],
            mode="explore",
            use_collaborative_flow=True,
        ).model_dump()
    )
    assert calls["n"] == MAX_SQL_ATTEMPTS
    assert result["sql_failed"] is True
    assert result["sql_retry_count"] == MAX_SQL_ATTEMPTS
    assert SQL_FAILED_SUMMARY_TH in result["query_result"]
    assert "Traceback" not in result["query_result"]
    assert "SQL_ERROR:" not in result["query_result"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [
        Exception("Invalid column name 'X'. 42S22"),
        RowCountExceeded(90000, 50000),
        RuntimeError("Incorrect syntax near 'FROM'"),
    ],
)
async def test_fail_sql_attempt_logs_and_counts(temp_storage, monkeypatch, error):
    logged = []

    async def capture(theme_id, user_prompt, sql, error, retry_count):
        logged.append(
            {
                "theme_id": theme_id,
                "user_prompt": user_prompt,
                "sql": sql,
                "error": error,
                "retry_count": retry_count,
            }
        )

    monkeypatch.setattr(
        "backend.app.agents.data_analyst.log_sql_failure", capture
    )
    state = AgentState(sql_retry_count=0, messages=[HumanMessage(content="q")])
    out = await _fail_sql_attempt(state, "base", "SELECT 1", error, "sales", "q", [])
    assert out["sql_retry_count"] == 1
    assert out["sql_failed"] is False
    assert out["sql_error"]
    assert "Traceback" not in out["sql_error"]
    assert logged and logged[0]["retry_count"] == 1

    state2 = AgentState(sql_retry_count=2, messages=[HumanMessage(content="q")])
    out2 = await _fail_sql_attempt(state2, "base", "SELECT 1", error, "sales", "q", [])
    assert out2["sql_retry_count"] == 3
    assert out2["sql_failed"] is True
    assert SQL_FAILED_SUMMARY_TH in out2["query_result"]


@pytest.mark.anyio
async def test_data_analyst_column_error_enters_retry_state(temp_storage, monkeypatch):
    from backend.app.agents import data_analyst

    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: True)

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(
                content="ANALYSIS: draft\nSQL:\n```sql\nSELECT BADCOL FROM VBRK\n```\n"
            )

    monkeypatch.setattr(data_analyst, "llm", FakeLLM())
    monkeypatch.setattr(data_analyst, "read_trusted_layer", AsyncMock(return_value={"metrics": []}))

    async def boom_exec(sql, mode="explore"):
        raise Exception("Invalid column name 'BADCOL'. (42S22)")

    monkeypatch.setattr(data_analyst, "_execute_sql_with_guard", boom_exec)
    monkeypatch.setattr(
        "backend.app.agents.data_analyst.log_sql_failure", AsyncMock()
    )

    state = AgentState(
        thread_id="t-retry",
        mode="explore",
        discovery_context="## VBRK\n  - NETWR",
        messages=[HumanMessage(content="ยอด")],
    )
    result = await data_analyst_node(state)
    assert result["sql_retry_count"] == 1
    assert result["sql_failed"] is False
    assert result["sql_error"]
    assert "SQL_ERROR:" not in result["query_result"]
    assert after_analyst(AgentState(**{**state.model_dump(), **result})) == "retry_sql"


def test_graceful_degradation_in_quality_assembly(temp_storage, monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.quality_assembly.fabric_can_query", lambda: False
    )
    state = AgentState(
        thread_id="t-g",
        mode="explore",
        sql_failed=True,
        sql_retry_count=3,
        sql_error="ชื่อคอลัมน์ผิด",
        generated_sql="SELECT bad FROM t",
        query_result="SQL_ATTEMPT_FAILED: x\n\n" + SQL_FAILED_SUMMARY_TH,
        messages=[HumanMessage(content="คำถามกว้าง")],
        step_errors=["data_analyst SQL: ชื่อคอลัมน์ผิด"],
    )
    payload = build_quality_payload(state)
    assert payload["sql_failed"] is True
    assert payload["answer_summary_th"] == SQL_FAILED_CEO_MSG_TH
    rendered = format_explore_response_th(payload)
    assert "ลองปรับ SQL แล้ว 3 ครั้ง" in rendered
    assert "Traceback" not in rendered
    assert "SQL_ERROR:" not in rendered
