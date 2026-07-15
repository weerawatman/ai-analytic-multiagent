import pytest

from backend.app.services import backlog_store
from backend.app.services.phase1_validator import run_phase1_validation
from backend.app.services.promotion_service import approve_promotion
from backend.app.services.sql_guard import validate_read_only_sql


@pytest.mark.anyio
async def test_phase1_validation_all_pass_with_fixture_data(temp_storage) -> None:
    item = backlog_store.create_item(
        {
            "theme": "sales",
            "question_th": "ยอดขาย?",
            "answer_summary_th": "summary",
            "sql_primary": "SELECT 1",
            "sql_alternative": "SELECT COUNT(*) FROM t",
            "assumptions": ["grain: daily"],
            "confidence": "medium",
            "unknowns": ["u"],
            "questions_for_ba_da": ["q"],
            "sample_data_ref": "inline",
            "status": "validated",
        }
    )
    backlog_store.update_item(item["id"], {"feedback": "BA confirm"})

    await approve_promotion(item["id"], approved=True)

    from backend.app.services.report_generator import export_backlog_item

    export_backlog_item(backlog_store.get_item(item["id"]))

    report = await run_phase1_validation()
    assert report["summary"]["total"] >= 10
    assert report["checks"][0]["id"] == "AC-1-guard"
    assert report["checks"][0]["passed"] is True

    check_ids = {c["id"]: c["passed"] for c in report["checks"]}
    assert check_ids["AC-4"] is True
    assert check_ids["AC-6"] is True
    assert check_ids["AC-7"] is True
    assert check_ids["AC-8"] is True
    assert check_ids["AC-10"] is True


@pytest.mark.anyio
async def test_phase1_validation_empty_backlog(temp_storage) -> None:
    report = await run_phase1_validation()
    check_ids = {c["id"]: c for c in report["checks"]}
    assert check_ids["AC-4"]["passed"] is False
    assert check_ids["AC-7"]["passed"] is False
    assert report["summary"]["ready_for_signoff"] is False


def test_sql_guard_part_of_validation() -> None:
    assert validate_read_only_sql("SELECT 1") == "SELECT 1"
