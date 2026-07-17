"""PostgreSQL WH_Silver mirror connector — auto-fallback source."""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import MagicMock

import pytest

from backend.app.services.postgres_replica import (
    PostgresReplicaConnectionError,
    PostgresReplicaConnector,
)
from backend.app.services.sql_guard import SQLGuardError


def _settings(**overrides):
    from backend.app.core.config import Settings

    base = dict(
        pg_replica_host="172.16.0.70",
        pg_replica_port=5432,
        pg_replica_db="fabric_WH_Silver",
        pg_replica_user="postgres",
        pg_replica_password="secret",
        pg_replica_connect_timeout=10,
        pg_replica_query_timeout=300,
    )
    base.update(overrides)
    return Settings(**base)


def test_is_configured_requires_host_db_user():
    assert PostgresReplicaConnector(_settings()).is_configured() is True
    assert PostgresReplicaConnector(_settings(pg_replica_host="")).is_configured() is False
    assert PostgresReplicaConnector(_settings(pg_replica_db="")).is_configured() is False
    assert PostgresReplicaConnector(_settings(pg_replica_user="")).is_configured() is False


def test_is_configured_does_not_require_password():
    """A blank password is valid libpq usage (e.g. trust auth) — only host/db/user gate it."""
    assert PostgresReplicaConnector(_settings(pg_replica_password="")).is_configured() is True


def test_connect_raises_when_not_configured():
    connector = PostgresReplicaConnector(_settings(pg_replica_host=""))
    with pytest.raises(PostgresReplicaConnectionError):
        with connector.connect():
            pass


def test_connect_sets_readonly_and_statement_timeout(monkeypatch):
    connector = PostgresReplicaConnector(_settings(pg_replica_query_timeout=45))
    fake_cursor = MagicMock()
    fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
    fake_cursor.__exit__ = MagicMock(return_value=False)
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor

    captured = {}

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return fake_conn

    monkeypatch.setattr("backend.app.services.postgres_replica.psycopg2.connect", fake_connect)

    with connector.connect() as conn:
        assert conn is fake_conn

    assert captured["host"] == "172.16.0.70"
    assert captured["dbname"] == "fabric_WH_Silver"
    fake_conn.set_session.assert_called_once_with(readonly=True, autocommit=True)
    fake_cursor.execute.assert_called_once_with("SET statement_timeout = %s", (45000,))
    fake_conn.close.assert_called_once()


def test_execute_read_only_rejects_write_sql(monkeypatch):
    connector = PostgresReplicaConnector(_settings())
    with pytest.raises(SQLGuardError):
        connector.execute_read_only("DELETE FROM t")


def test_execute_read_only_runs_select_and_maps_rows(monkeypatch):
    connector = PostgresReplicaConnector(_settings())

    # psycopg2's cursor.description entries are Column objects with a `.name`
    # attribute — not plain tuples — so the fake must match that shape.
    Col = namedtuple("Col", ["name"])
    fake_cursor = MagicMock()
    fake_cursor.description = [Col("a"), Col("b")]
    fake_cursor.fetchmany.return_value = [(1, "x"), (2, "y")]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor

    class FakeCtx:
        def __enter__(self):
            return fake_conn

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(connector, "connect", lambda: FakeCtx())

    result = connector.execute_read_only("SELECT a, b FROM t", mode="explore", max_rows=5)
    assert result["columns"] == ["a", "b"]
    assert result["rows"] == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    assert result["row_count"] == 2
    fake_cursor.execute.assert_called_once_with("SELECT a, b FROM t")


def test_fetch_schema_summary_uses_limit_not_top(monkeypatch):
    """Postgres dialect: LIMIT, never T-SQL's TOP (would be a syntax error here)."""
    connector = PostgresReplicaConnector(_settings())
    captured_sql = {}

    def fake_execute_read_only(sql, *, mode="explore", max_rows=None):
        captured_sql["sql"] = sql
        return {"rows": [{"table_schema": "public", "table_name": "vbrk", "table_type": "BASE TABLE"}]}

    monkeypatch.setattr(connector, "execute_read_only", fake_execute_read_only)
    rows = connector.fetch_schema_summary(top_schemas=5)
    assert rows[0]["table_name"] == "vbrk"
    assert "LIMIT 250" in captured_sql["sql"]
    assert "TOP" not in captured_sql["sql"].upper()


def test_fetch_schema_summary_excludes_postgres_system_catalogs(monkeypatch):
    """Regression: information_schema.tables lists pg_catalog/information_schema
    themselves (unlike SQL Server) — without this filter a live check against
    the real WH_Silver mirror returned 226 "tables" (17 real SAPHANADB tables
    + 209 Postgres system catalog entries)."""
    connector = PostgresReplicaConnector(_settings())
    captured_sql = {}

    def fake_execute_read_only(sql, *, mode="explore", max_rows=None):
        captured_sql["sql"] = sql
        return {"rows": []}

    monkeypatch.setattr(connector, "execute_read_only", fake_execute_read_only)
    connector.fetch_schema_summary(top_schemas=5)
    assert "NOT IN ('pg_catalog', 'information_schema')" in captured_sql["sql"]
