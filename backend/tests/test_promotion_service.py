import pytest

from backend.app.services import backlog_store
from backend.app.services.promotion_service import (
    approve_promotion,
    build_metric_preview,
    get_promotion_preview,
)
from backend.app.services.semantic_store import read_trusted_layer


def test_build_metric_preview_from_backlog(temp_storage) -> None:
    item = backlog_store.create_item(
        {
            "theme": "sales",
            "question_th": "ยอดขายรายเดือน?",
            "answer_summary_th": "ยอดขายรวมตาม order completed",
            "sql_primary": "SELECT SUM(amount) FROM orders",
            "assumptions": ["grain: monthly", "filter: status = completed"],
            "questions_for_ba_da": ["รวม VAT หรือไม่?"],
            "status": "validated",
        }
    )

    metric = build_metric_preview(item)
    assert metric["metric_key"].startswith("sales_")
    assert metric["sql_template"] == "SELECT SUM(amount) FROM orders"
    assert metric["grain"] == "monthly"
    assert "status = completed" in metric["standard_filters"][0]
    assert metric["source_backlog_id"] == item["id"]


@pytest.mark.anyio
async def test_promotion_preview_and_approve(temp_storage) -> None:
    item = backlog_store.create_item(
        {
            "theme": "inventory",
            "question_th": "สต็อกคงเหลือ?",
            "answer_summary_th": "qty on hand",
            "sql_primary": "SELECT SUM(qty) FROM stock",
            "status": "validated",
        }
    )

    preview = get_promotion_preview(item["id"])
    assert preview["item_id"] == item["id"]
    assert "preview_markdown" in preview
    assert preview["metric"]["theme"] == "inventory"

    result = await approve_promotion(item["id"], approved=True, approved_by="de_user")
    assert result["status"] == "promoted"
    assert result["metric"]["metric_key"]

    updated = backlog_store.get_item(item["id"])
    assert updated["status"] == "promoted"

    trusted = await read_trusted_layer()
    assert any(m["metric_key"] == result["metric"]["metric_key"] for m in trusted["metrics"])


@pytest.mark.anyio
async def test_promotion_reject_keeps_backlog_status(temp_storage) -> None:
    item = backlog_store.create_item(
        {
            "theme": "sales",
            "question_th": "reject test",
            "status": "validated",
        }
    )
    result = await approve_promotion(item["id"], approved=False)
    assert result["status"] == "cancelled"
    assert backlog_store.get_item(item["id"])["status"] == "validated"
