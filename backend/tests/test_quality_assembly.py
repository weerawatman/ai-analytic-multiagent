from langchain_core.messages import HumanMessage

from backend.app.agents.state import AgentState
from backend.app.services.quality_assembly import (
    build_quality_payload,
    format_explore_response_th,
    validate_quality_bar_d,
)


def test_build_quality_payload_from_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.quality_assembly.fabric_can_query", lambda: False
    )
    state = AgentState(
        thread_id="t1",
        mode="explore",
        theme="sales",
        messages=[HumanMessage(content="ยอดขายเป็นอย่างไร?")],
        generated_sql="SELECT 1 AS n",
        query_result="SQL: SELECT 1 AS n\nANALYSIS: ยอดขายโต\nASSUMPTIONS:\n- daily grain",
        analysis_summary="ALT_SQL: SELECT COUNT(*) AS c\nQUESTIONS_FOR_BA_DA:\n- รวม VAT ไหม?",
    )
    payload = build_quality_payload(state)
    assert payload["question_th"] == "ยอดขายเป็นอย่างไร?"
    assert payload["sql_primary"] == "SELECT 1 AS n"
    assert payload["assumptions"]
    assert payload["questions_for_ba_da"]
    assert "data_analyst" in payload.get("agents_involved", [])
    assert "data_scientist" in payload.get("agents_involved", [])
    assert payload.get("sample_data_ref") == "skipped_offline"


def test_format_includes_data_scientist_section() -> None:
    text = format_explore_response_th(
        {
            "answer_summary_th": "สรุป",
            "sql_primary": "SELECT 1",
            "assumptions": ["a"],
            "unknowns": ["u"],
            "questions_for_ba_da": ["q"],
            "confidence": "medium",
            "scientist_critique_th": "CRITIQUE: ควรตรวจ grain รายวัน",
        }
    )
    assert "Data Scientist" in text
    assert "grain" in text


def test_format_explore_response_th() -> None:
    text = format_explore_response_th(
        {
            "answer_summary_th": "สรุป",
            "sql_primary": "SELECT 1",
            "assumptions": ["a"],
            "unknowns": ["u"],
            "questions_for_ba_da": ["q"],
            "confidence": "medium",
        }
    )
    assert "Draft" in text
    assert "SELECT 1" in text


def test_validate_quality_bar_d() -> None:
    missing = validate_quality_bar_d({"sql_primary": "SELECT 1"})
    assert "assumptions" in missing


def test_sample_query_respects_row_count_guard(monkeypatch) -> None:
    """Sample-row re-execution must go through the pre-flight COUNT(*) guard —
    an oversized query is skipped with a polite note, never re-scanned."""
    from backend.app.services import quality_assembly
    from backend.app.services.fabric_sql import RowCountExceeded

    monkeypatch.setattr(quality_assembly, "fabric_can_query", lambda: True)

    def raise_exceeded(sql, settings=None):
        raise RowCountExceeded(estimated=999999, threshold=50000)

    monkeypatch.setattr(quality_assembly, "enforce_row_count_threshold", raise_exceeded)

    def must_not_run(*args, **kwargs):
        raise AssertionError("run_fabric_sql must not be reached when the guard rejects")

    monkeypatch.setattr(quality_assembly, "run_fabric_sql", must_not_run)

    state = AgentState(
        thread_id="t-guard",
        mode="explore",
        messages=[HumanMessage(content="ยอดขายทั้งตาราง")],
        generated_sql="SELECT * FROM VBRK",
        query_result="SQL: SELECT * FROM VBRK\nANALYSIS: กว้างมาก",
    )
    payload = quality_assembly.build_quality_payload(state)
    assert payload["sample_data_ref"] == "skipped_row_count"
    assert "เกินเกณฑ์" in payload["sample_preview"]


def test_sample_query_runs_when_guard_passes(monkeypatch) -> None:
    from backend.app.services import quality_assembly

    monkeypatch.setattr(quality_assembly, "fabric_can_query", lambda: True)
    monkeypatch.setattr(
        quality_assembly, "enforce_row_count_threshold", lambda sql, settings=None: 10
    )
    monkeypatch.setattr(
        quality_assembly,
        "run_fabric_sql",
        lambda sql, *, mode="explore", max_rows=None: {"rows": [{"n": 1}], "columns": ["n"]},
    )

    state = AgentState(
        thread_id="t-guard-ok",
        mode="explore",
        messages=[HumanMessage(content="ยอดขาย")],
        generated_sql="SELECT TOP 5 n FROM t",
        query_result="SQL: SELECT TOP 5 n FROM t\nANALYSIS: เล็ก",
    )
    payload = quality_assembly.build_quality_payload(state)
    assert payload["sample_data_ref"] == "inline"
    assert '"n": 1' in payload["sample_preview"]
