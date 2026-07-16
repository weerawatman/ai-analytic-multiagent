"""Tests for CEO feedback store."""

from backend.app.services.feedback_store import add_feedback, format_feedback_context, load_feedback


def test_add_and_load_feedback(temp_storage):
    theme_id = "theme-sales"
    add_feedback(
        theme_id,
        brief_id="b1",
        role="data_analyst",
        action="approve",
        comment="ใช้ FKDAT เป็นวันที่",
    )
    data = load_feedback(theme_id)
    assert len(data["entries"]) == 1
    assert data["entries"][0]["action"] == "approve"


def test_format_feedback_context(temp_storage):
    theme_id = "theme-sales"
    add_feedback(
        theme_id,
        brief_id="b2",
        role="business_analyst",
        action="reject",
        comment="นิยามยอดขายไม่ชัด",
    )
    ctx = format_feedback_context(theme_id)
    assert "CEO Feedback" in ctx
    assert "reject" in ctx
