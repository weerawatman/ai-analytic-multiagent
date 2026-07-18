"""sql_error_classifier tests (Phase J) — pure classification, no I/O."""

from __future__ import annotations

import pytest

from backend.app.services.fabric_sql import RowCountExceeded
from backend.app.services.sql_error_classifier import classify_sql_error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RowCountExceeded(99_999, 50_000), "row_count"),
        ("ผลลัพธ์เกินเกณฑ์ที่กำหนด", "row_count"),
        ("query exceeds threshold of 50000 rows", "row_count"),
        ("Invalid column name 'FOO'. (42S22)", "invalid_column"),
        ("ชื่อคอลัมน์ไม่ถูกต้อง", "invalid_column"),
        ("column \"foo\" does not exist", "invalid_column"),
        ("ERROR: 42703 undefined_column", "invalid_column"),
        (TimeoutError("HYT00 Query timeout expired"), "timeout"),
        ("statement timed out (57014)", "timeout"),
        ("query เกินเวลาที่กำหนด", "timeout"),
        (RuntimeError("Login failed for user"), "connection"),
        ("could not connect to server", "connection"),
        ("connection refused (08006)", "connection"),
        ("เชื่อมต่อฐานข้อมูลไม่ได้", "connection"),
        (RuntimeError("syntax near 'FROM'"), "generic"),
    ],
)
def test_classify_sql_error(error, expected: str):
    assert classify_sql_error(error) == expected


def test_data_analyst_reexports_same_classifier():
    """Backward-compat alias in data_analyst must stay wired to the extracted module."""
    from backend.app.agents.data_analyst import _classify_sql_error

    assert _classify_sql_error is classify_sql_error
