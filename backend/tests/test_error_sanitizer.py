"""Unit tests for error_sanitizer — CEO/job-facing step notes."""

from backend.app.services.error_sanitizer import (
    SANITIZED_NOTE_TH,
    sanitize_error_entry,
    sanitize_step_errors,
)


def test_strips_raw_exception_detail():
    raw = (
        "data_analyst SQL: รัน SQL ไม่สำเร็จ "
        "(ProgrammingError: ('42000', '[Microsoft][ODBC Driver 18]...'))"
    )
    out = sanitize_error_entry(raw)
    assert out.startswith("data_analyst SQL:")
    assert SANITIZED_NOTE_TH in out
    assert "ProgrammingError" in out
    for banned in ("ODBC", "42000", "Microsoft", "Driver"):
        assert banned not in out


def test_keeps_clean_thai_guidance_notes():
    clean = (
        "data_analyst SQL: จำนวนแถวโดยประมาณ 99,999 เกินเกณฑ์ 50,000 "
        "— กรุณาจำกัดด้วย WHERE"
    )
    assert sanitize_error_entry(clean) == clean


def test_extracts_exception_type_from_common_patterns():
    already = "ชื่อคอลัมน์ใน SQL ไม่ถูกต้อง (ProgrammingError)"
    assert sanitize_error_entry(already) == already

    with_noise = "business_analyst: boom RuntimeError: connection reset by peer"
    out = sanitize_error_entry(with_noise)
    assert out.startswith("business_analyst:")
    assert "RuntimeError" in out
    assert SANITIZED_NOTE_TH in out
    assert "connection reset" not in out


def test_does_not_destroy_row_count_thai_messages():
    row = (
        "จำนวนแถวโดยประมาณ 12,345 เกินเกณฑ์ 10,000 "
        "— กรุณาจำกัดช่วงเวลาหรือหน่วยงานด้วย WHERE"
    )
    assert sanitize_error_entry(row) == row


def test_sanitize_step_errors_list():
    cleaned = sanitize_step_errors(
        [
            "data_analyst SQL: fail (OperationalError: HYT00 timeout)",
            "จำนวนแถวโดยประมาณ 1 เกินเกณฑ์ 1 — กรุณาจำกัดด้วย WHERE",
        ]
    )
    assert len(cleaned) == 2
    assert "OperationalError" in cleaned[0]
    assert "HYT00" not in cleaned[0]
    assert "เกินเกณฑ์" in cleaned[1]
