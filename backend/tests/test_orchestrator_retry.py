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
from backend.app.agents.orchestrator import after_analyst, summarize_node
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
    assert after_analyst(state) == "business_analyst"


def test_after_analyst_trusted_path_without_error():
    state = AgentState(mode="trusted", use_collaborative_flow=False, sql_error="")
    assert after_analyst(state) == "summarize"


def test_after_analyst_trusted_sql_failed_goes_to_summarize():
    state = AgentState(
        mode="trusted",
        use_collaborative_flow=False,
        sql_error="still broken",
        sql_failed=True,
        sql_retry_count=MAX_SQL_ATTEMPTS,
    )
    assert after_analyst(state) == "summarize"


@pytest.mark.anyio
async def test_trusted_sql_failed_final_answer_is_polite():
    """Trusted path has no quality_assembly cleanup — summarize itself must not
    concatenate raw SQL failure text into the CEO-facing answer."""
    state = AgentState(
        mode="trusted",
        use_collaborative_flow=False,
        sql_failed=True,
        sql_retry_count=MAX_SQL_ATTEMPTS,
        sql_error="รัน SQL ไม่สำเร็จ (ProgrammingError: '42000' ODBC)",
        query_result=(
            "ANALYSIS: Trusted ยอดขาย\n\n"
            "SQL_ATTEMPT_FAILED: รัน SQL ไม่สำเร็จ (ProgrammingError: ('42000', "
            "'[42000] [Microsoft][ODBC Driver 18 for SQL Server]...'))\n\n"
            + SQL_FAILED_SUMMARY_TH
        ),
        messages=[HumanMessage(content="ยอดขายเดือนนี้")],
    )
    out = await summarize_node(state)
    assert out["final_answer"] == SQL_FAILED_CEO_MSG_TH
    for banned in ("SQL_ATTEMPT_FAILED", "Traceback", "ProgrammingError", "ODBC", "42000"):
        assert banned not in out["final_answer"]


@pytest.mark.anyio
async def test_summarize_without_failure_unchanged():
    state = AgentState(
        mode="trusted",
        query_result="ANALYSIS: Trusted ยอดขาย 100 ล้านบาท",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    out = await summarize_node(state)
    assert "ANALYSIS: Trusted ยอดขาย 100 ล้านบาท" in out["final_answer"]


def test_error_classes_have_retry_guidance():
    assert _classify_sql_error(RowCountExceeded(99999, 50000)) == "row_count"
    assert _classify_sql_error("Invalid column name 'FOO'. (42S22)") == "invalid_column"
    assert _classify_sql_error(TimeoutError("HYT00 Query timeout expired")) == "timeout"
    assert _classify_sql_error(RuntimeError("Login failed for user")) == "connection"
    assert _classify_sql_error(RuntimeError("syntax near")) == "generic"
    for klass in ("row_count", "invalid_column", "timeout", "connection", "generic"):
        text = _retry_guidance(klass, "detail")
        assert "Error detail" in text
        assert len(text) > 20


def test_friendly_sql_error_omits_raw_odbc():
    from backend.app.agents.data_analyst import _friendly_sql_error

    raw = Exception(
        "[42000] [Microsoft][ODBC Driver 18 for SQL Server]Incorrect syntax near 'FROM'"
    )
    friendly = _friendly_sql_error(raw)
    assert friendly == "รัน SQL ไม่สำเร็จ (Exception)"
    for banned in ("ODBC", "42000", "Microsoft", "Incorrect syntax", "FROM"):
        assert banned not in friendly

    col = Exception("Invalid column name 'BADCOL'. (42S22)")
    assert _friendly_sql_error(col) == "ชื่อคอลัมน์ใน SQL ไม่ถูกต้อง (Exception)"
    assert "BADCOL" not in _friendly_sql_error(col)

    timed = TimeoutError("HYT00 Query timeout expired")
    assert "เกินเวลา" in _friendly_sql_error(timed)
    assert "HYT00" not in _friendly_sql_error(timed)


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
        {
            "retry_sql": "data_analyst",
            "business_analyst": "done",
            "explore_critique": "done",
            "summarize": "done",
        },
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

    async def capture(theme_id, user_prompt, sql, error, retry_count, source="fabric"):
        logged.append(
            {
                "theme_id": theme_id,
                "user_prompt": user_prompt,
                "sql": sql,
                "error": error,
                "retry_count": retry_count,
                "source": source,
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
    # Surface must not embed raw exception / ODBC detail — type + class only.
    assert "Incorrect syntax" not in out["sql_error"]
    assert "42S22" not in out["sql_error"]
    assert "Invalid column" not in out["sql_error"]
    assert logged and logged[0]["retry_count"] == 1
    # PDCA (file-only) still receives the full exception text for debugging.
    assert ":" in logged[0]["error"]

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


@pytest.mark.anyio
async def test_data_analyst_retry_success_clears_sql_error(temp_storage, monkeypatch):
    """Attempt 2 fixes the SQL: sql_error must be cleared and the loop must exit."""
    from backend.app.agents import data_analyst

    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: True)

    class FixItLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content="```sql\nSELECT NETWR FROM VBRK\n```")

    monkeypatch.setattr(data_analyst, "llm", FixItLLM())
    monkeypatch.setattr(data_analyst, "read_trusted_layer", AsyncMock(return_value={"metrics": []}))
    monkeypatch.setattr(
        data_analyst, "enforce_row_count_threshold_for_source_async", AsyncMock(return_value=10)
    )
    monkeypatch.setattr(
        data_analyst,
        "run_sql_async",
        AsyncMock(return_value={"rows": [{"NETWR": 100}], "columns": ["NETWR"], "source": "fabric"}),
    )

    state = AgentState(
        thread_id="t-retry-ok",
        mode="explore",
        discovery_context="## VBRK\n  - NETWR",
        generated_sql="SELECT BADCOL FROM VBRK",
        query_result="ANALYSIS: draft\nSQL_ATTEMPT_FAILED: ชื่อคอลัมน์ผิด",
        sql_error="Invalid column name 'BADCOL'. (42S22)",
        sql_retry_count=1,
        messages=[HumanMessage(content="ยอดขาย")],
    )
    result = await data_analyst_node(state)
    assert result["sql_error"] == ""
    assert result["sql_failed"] is False
    assert result["generated_sql"] == "SELECT NETWR FROM VBRK"
    assert "QUERY_RESULT" in result["query_result"]
    merged = AgentState(**{**state.model_dump(), **result})
    assert after_analyst(merged) != "retry_sql"


@pytest.mark.anyio
async def test_trusted_retry_success_strips_prior_attempt_text(temp_storage, monkeypatch):
    """Trusted mode, retry succeeds on attempt 2 — final_answer must carry no
    SQL_ATTEMPT_FAILED marker nor exception-type text from the failed attempt."""
    from backend.app.agents import data_analyst

    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: True)

    class FixItLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content="```sql\nSELECT NETWR FROM VBRK\n```")

    monkeypatch.setattr(data_analyst, "llm", FixItLLM())
    monkeypatch.setattr(
        data_analyst,
        "read_trusted_layer",
        AsyncMock(return_value={"metrics": [{"metric_key": "total_sales", "theme": ""}]}),
    )
    monkeypatch.setattr(
        data_analyst, "enforce_row_count_threshold_for_source_async", AsyncMock(return_value=10)
    )
    monkeypatch.setattr(
        data_analyst,
        "run_sql_async",
        AsyncMock(return_value={"rows": [{"NETWR": 100}], "columns": ["NETWR"], "source": "fabric"}),
    )

    state = AgentState(
        thread_id="t-trusted-retry-ok",
        mode="trusted",
        use_collaborative_flow=False,
        discovery_context="## VBRK\n  - NETWR",
        generated_sql="SELECT BADCOL FROM VBRK",
        query_result=(
            "ANALYSIS: Trusted ยอดขาย\n\n"
            "SQL_ATTEMPT_FAILED: รัน SQL ไม่สำเร็จ (ProgrammingError: ('42000', "
            "'[42000] [Microsoft][ODBC Driver 18 for SQL Server]...'))"
        ),
        sql_error="Invalid column name 'BADCOL'. (42S22)",
        sql_retry_count=1,
        messages=[HumanMessage(content="ยอดขายเดือนนี้")],
    )
    result = await data_analyst_node(state)
    assert result["sql_error"] == ""
    assert result["sql_failed"] is False

    merged = AgentState(**{**state.model_dump(), **result})
    assert after_analyst(merged) == "summarize"
    out = await summarize_node(merged)
    final = out["final_answer"]
    assert "QUERY_RESULT" in final  # successful result present
    assert "ANALYSIS: Trusted ยอดขาย" in final  # analytic portion preserved
    for banned in ("SQL_ATTEMPT_FAILED", "ProgrammingError", "ODBC", "42000", "Traceback"):
        assert banned not in final


@pytest.mark.anyio
async def test_explore_critique_skips_llm_when_sql_failed(temp_storage, monkeypatch):
    """DS critique on failed SQL must be deterministic — no LLM echo of errors."""
    from backend.app.agents import data_scientist
    from backend.app.agents.data_scientist import SQL_FAILED_CRITIQUE_TH, explore_critique_node

    class BoomLLM:
        async def ainvoke(self, messages):
            raise AssertionError("LLM must not be called when sql_failed=True")

    monkeypatch.setattr(data_scientist, "llm", BoomLLM())

    state = AgentState(
        thread_id="t-ds-skip",
        mode="explore",
        sql_failed=True,
        sql_retry_count=MAX_SQL_ATTEMPTS,
        query_result="SQL_ATTEMPT_FAILED: รัน SQL ไม่สำเร็จ (ProgrammingError: ODBC ...)",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    out = await explore_critique_node(state)
    assert out["analysis_summary"] == SQL_FAILED_CRITIQUE_TH
    for banned in ("SQL_ATTEMPT_FAILED", "ProgrammingError", "ODBC", "Traceback"):
        assert banned not in out["analysis_summary"]


@pytest.mark.anyio
async def test_data_engineer_inspection_sql_error_not_raw(temp_storage, monkeypatch):
    """DE inspection-SQL failure must not append raw `SQL_ERROR: {e}` to content."""
    from backend.app.agents import data_engineer
    from backend.app.agents.data_engineer import data_engineer_node

    class DELLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(
                content=(
                    "SCHEMA: ตาราง VBRK\nSEMANTIC_UPDATE: none\nSUMMARY: สรุป\n"
                    "SQL:\n```sql\nSELECT TOP 5 * FROM VBRK\n```"
                )
            )

    monkeypatch.setattr(data_engineer, "llm", DELLM())
    monkeypatch.setattr(data_engineer, "fabric_can_query", lambda: True)
    monkeypatch.setattr(
        data_engineer, "read_semantic_layer", AsyncMock(return_value="(empty)")
    )

    async def odbc_boom(sql, *, mode="explore", max_rows=None):
        raise RuntimeError("('42000', '[42000] [Microsoft][ODBC Driver 18 for SQL Server]...')")

    monkeypatch.setattr(data_engineer, "run_fabric_sql_async", odbc_boom)

    state = AgentState(
        thread_id="t-de",
        mode="explore",
        discovery_context="## VBRK",
        messages=[HumanMessage(content="โครงสร้างตาราง")],
    )
    out = await data_engineer_node(state)
    content = out["schema_info"]
    assert "SQL_ERROR:" not in content
    assert "ODBC" not in content
    assert "42000" not in content
    assert "SQL_SKIPPED" in content
    # step_errors keep the detail for internal diagnostics.
    assert out["step_errors"] and "ODBC" in out["step_errors"][0]


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
