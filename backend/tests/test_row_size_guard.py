"""Phase D1 — pre-flight COUNT(*) row-size guard."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.app.services import fabric_sql
from backend.app.services.fabric_sql import (
    RowCountExceeded,
    build_count_guard_sql,
    enforce_row_count_threshold,
    estimate_row_count,
    strip_trailing_order_by,
)


def test_strip_trailing_order_by_simple():
    sql = "SELECT a, b FROM t WHERE x = 1 ORDER BY a DESC"
    assert strip_trailing_order_by(sql) == "SELECT a, b FROM t WHERE x = 1"


def test_strip_trailing_order_by_with_top():
    sql = "SELECT TOP 10 NETWR, KUNAG FROM VBRK ORDER BY NETWR DESC"
    assert "ORDER BY" not in strip_trailing_order_by(sql).upper()
    assert "TOP 10" in strip_trailing_order_by(sql).upper()


def test_build_count_guard_sql_strips_order_by():
    sql = "SELECT TOP 5 * FROM CE1SATG ORDER BY WW005 DESC"
    wrapped = build_count_guard_sql(sql)
    assert wrapped.upper().startswith("SELECT COUNT(*)")
    assert "_guard_cnt" in wrapped
    # Inner query must not end with ORDER BY (SQL Server error 1033).
    inner_start = wrapped.index("(") + 1
    inner_end = wrapped.rindex(")")
    inner = wrapped[inner_start:inner_end]
    assert "ORDER BY" not in inner.upper()


def test_estimate_row_count_happy_path(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_ROW_COUNT_THRESHOLD", "50000")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    def fake_run(sql, *, mode="explore", max_rows=None):
        assert "COUNT(*)" in sql.upper()
        assert "ORDER BY" not in sql.upper().split("FROM")[-1] or "_guard_cnt" in sql
        return {"rows": [{"cnt": 42}], "columns": ["cnt"]}

    monkeypatch.setattr(fabric_sql, "run_fabric_sql", fake_run)
    n = estimate_row_count("SELECT a FROM t ORDER BY a")
    assert n == 42
    get_settings.cache_clear()


def test_enforce_threshold_raises_structured_error(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_ROW_COUNT_THRESHOLD", "100")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(fabric_sql, "estimate_row_count", lambda sql, settings=None: 500)
    with pytest.raises(RowCountExceeded) as ei:
        enforce_row_count_threshold("SELECT * FROM big")
    assert ei.value.estimated == 500
    assert ei.value.threshold == 100
    assert "WHERE" in str(ei.value) or "Narrow" in str(ei.value)
    assert ei.value.message_th
    get_settings.cache_clear()


def test_estimate_fail_open_on_wrap_or_count_failure(temp_storage, monkeypatch):
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    def boom(*a, **k):
        raise RuntimeError("weird parse")

    monkeypatch.setattr(fabric_sql, "run_fabric_sql", boom)
    # Valid SELECT — wrap succeeds, count execution fails → fail-open None
    assert estimate_row_count("SELECT 1 AS x") is None

    # Broken build path
    monkeypatch.setattr(
        fabric_sql,
        "build_count_guard_sql",
        MagicMock(side_effect=ValueError("cannot wrap")),
    )
    assert estimate_row_count("SELECT 1 AS x") is None
    get_settings.cache_clear()


def test_enforce_fail_open_does_not_block(temp_storage, monkeypatch):
    monkeypatch.setattr(fabric_sql, "estimate_row_count", lambda sql, settings=None: None)
    assert enforce_row_count_threshold("SELECT 1") is None
