import pytest

from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql


def test_validate_select_ok() -> None:
    sql = "SELECT 1 AS ok"
    assert validate_read_only_sql(sql) == sql


def test_validate_cte_ok() -> None:
    sql = "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte"
    assert "WITH cte" in validate_read_only_sql(sql)


def test_reject_delete() -> None:
    with pytest.raises(SQLGuardError) as exc:
        validate_read_only_sql("DELETE FROM sales")
    assert exc.value.message_th


def test_reject_insert() -> None:
    with pytest.raises(SQLGuardError):
        validate_read_only_sql("INSERT INTO t VALUES (1)")


def test_reject_multiple_statements() -> None:
    with pytest.raises(SQLGuardError):
        validate_read_only_sql("SELECT 1; SELECT 2")


def test_reject_empty() -> None:
    with pytest.raises(SQLGuardError):
        validate_read_only_sql("   ")
