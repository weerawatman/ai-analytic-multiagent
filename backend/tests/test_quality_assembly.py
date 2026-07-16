from langchain_core.messages import HumanMessage

from backend.app.agents.state import AgentState
from backend.app.services.quality_assembly import (
    build_quality_payload,
    format_explore_response_th,
    validate_quality_bar_d,
)


def test_build_quality_payload_from_state() -> None:
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
