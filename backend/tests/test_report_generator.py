from backend.app.services.report_generator import render_handoff_markdown


def test_render_handoff_markdown_th() -> None:
    item = {
        "id": "abc-123",
        "theme": "sales",
        "mode": "explore",
        "status": "new",
        "question_th": "ยอดขายเป็นอย่างไร?",
        "answer_summary_th": "ยอดโต 10%",
        "sql_primary": "SELECT 1",
        "sql_alternative": "SELECT COUNT(*) FROM t",
        "assumptions": ["daily grain"],
        "confidence": "medium",
        "unknowns": ["VAT?"],
        "questions_for_ba_da": ["รวม VAT ไหม?"],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "ba_da_feedback": [],
    }
    md = render_handoff_markdown(item)
    assert "ยอดขายเป็นอย่างไร" in md
    assert "SELECT 1" in md
    assert "BA/DA" in md
    assert "Draft" in md


def test_export_backlog_item_writes_file(temp_storage) -> None:
    from backend.app.services import backlog_store
    from backend.app.services.report_generator import export_backlog_item

    item = backlog_store.create_item(
        {
            "theme": "sales",
            "question_th": "ทดสอบ export",
            "answer_summary_th": "สรุป",
            "sql_primary": "SELECT 1",
            "assumptions": ["test"],
            "questions_for_ba_da": ["q1"],
        }
    )
    result = export_backlog_item(item)
    assert result["filename"].endswith(".md")
    assert "ทดสอบ export" in result["content"]
