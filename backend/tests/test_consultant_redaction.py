"""Tests for consultant redaction whitelist."""

from backend.app.services.consultant_redaction import (
    build_consultant_sections,
    redact_for_external,
)


def test_redact_query_result_blocks():
    text = "SUMMARY: ok\nQUERY_RESULT:\n[{'a': 1}]\nNEXT"
    out = redact_for_external(text)
    assert "[{'a': 1}]" not in out
    assert "ข้อมูลระดับแถวถูกตัดออก" in out


def test_redact_sql_result_and_retry():
    text = "SQL_RESULT:\n[{'x': 2}]\nSQL_RETRY:\n[{'y': 3}]"
    out = redact_for_external(text)
    assert "[{'x': 2}]" not in out
    assert "[{'y': 3}]" not in out


def test_redact_sample_section():
    text = "### ตัวอย่างข้อมูล\n```json\n[{\"NetValue\": 100}]\n```\nหลัง"
    out = redact_for_external(text)
    assert "NetValue" not in out
    assert "ข้อมูลระดับแถวถูกตัดออก" in out


def test_sections_never_include_sample_preview(temp_storage, monkeypatch):
    monkeypatch.setenv("CONSULTANT_MAX_SECTION_CHARS", "100")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    sections = build_consultant_sections(
        theme_id="t1",
        theme="sales",
        question="q",
        draft_answer="answer",
        quality_payload={
            "sql_primary": "SELECT 1",
            "sample_preview": [{"secret": 99}],
            "quality_gaps": ["assumptions"],
        },
        step_errors=["da boom"],
    )
    blob = " ".join(sections.values())
    assert "secret" not in blob
    assert "sample_preview" not in blob
    assert "sql_primary" in sections
    # Cap applied
    for v in sections.values():
        assert len(v) <= 100
    get_settings.cache_clear()
