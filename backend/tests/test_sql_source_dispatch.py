"""Fabric-primary / Postgres-replica auto-fallback dispatch.

The Postgres WH_Silver mirror is a same-data alternative source, wired in
because Fabric capacity has been unreliable. Fabric is always preferred;
Postgres is only used when Fabric is unreachable/paused/disabled.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.app.services import fabric_sql
from backend.app.services.fabric_connector import FabricConnectionError


@pytest.fixture(autouse=True)
def _reset_reachability_caches():
    fabric_sql.clear_reachability_cache()
    fabric_sql.clear_pg_reachability_cache()
    yield
    fabric_sql.clear_reachability_cache()
    fabric_sql.clear_pg_reachability_cache()


def _configure_fabric(monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENABLED", "true")
    monkeypatch.setenv("FABRIC_SERVER", "x.example.com")
    monkeypatch.setenv("FABRIC_DATABASE", "WH")
    monkeypatch.setenv("FABRIC_TENANT_ID", "t")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "c")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "s")


def _configure_pg(monkeypatch):
    monkeypatch.setenv("PG_REPLICA_HOST", "172.16.0.70")
    monkeypatch.setenv("PG_REPLICA_DB", "fabric_WH_Silver")
    monkeypatch.setenv("PG_REPLICA_USER", "postgres")
    monkeypatch.setenv("PG_REPLICA_PASSWORD", "secret")


def _blank_both_sources(monkeypatch):
    """Force both sources 'unconfigured' regardless of the repo's real .env
    (live Fabric creds) or a same-process singleton already constructed from
    it by an earlier test — mock the connector getters directly rather than
    trusting env-var overrides alone, since `get_fabric_connector()` caches
    its instance (and the settings it captured) for the life of the process.
    """
    for key in (
        "FABRIC_SERVER",
        "FABRIC_DATABASE",
        "FABRIC_TENANT_ID",
        "FABRIC_CLIENT_ID",
        "FABRIC_CLIENT_SECRET",
        "PG_REPLICA_HOST",
        "PG_REPLICA_DB",
        "PG_REPLICA_USER",
    ):
        monkeypatch.setenv(key, "")
    unconfigured = MagicMock()
    unconfigured.is_configured.return_value = False
    monkeypatch.setattr(fabric_sql, "get_fabric_connector", lambda: unconfigured)
    monkeypatch.setattr(fabric_sql, "get_postgres_connector", lambda: unconfigured)


def _clear_settings_cache():
    from backend.app.core.config import get_settings

    get_settings.cache_clear()


def test_get_active_sql_source_prefers_fabric(temp_storage, monkeypatch):
    _configure_fabric(monkeypatch)
    _configure_pg(monkeypatch)
    _clear_settings_cache()

    fake_fabric = MagicMock()
    fake_fabric.is_configured.return_value = True
    fake_fabric.ping.return_value = {"connected": True}
    monkeypatch.setattr(fabric_sql, "get_fabric_connector", lambda: fake_fabric)

    assert fabric_sql.get_active_sql_source() == "fabric"
    _clear_settings_cache()


def test_get_active_sql_source_falls_back_to_postgres_when_fabric_down(temp_storage, monkeypatch):
    _configure_fabric(monkeypatch)
    _configure_pg(monkeypatch)
    _clear_settings_cache()

    fake_fabric = MagicMock()
    fake_fabric.is_configured.return_value = True
    fake_fabric.ping.side_effect = FabricConnectionError("capacity paused", "pause")
    monkeypatch.setattr(fabric_sql, "get_fabric_connector", lambda: fake_fabric)

    fake_pg = MagicMock()
    fake_pg.is_configured.return_value = True
    fake_pg.ping.return_value = {"connected": True}
    monkeypatch.setattr(fabric_sql, "get_postgres_connector", lambda: fake_pg)

    assert fabric_sql.get_active_sql_source() == "postgres"
    _clear_settings_cache()


def test_get_active_sql_source_offline_when_both_down(temp_storage, monkeypatch):
    _blank_both_sources(monkeypatch)
    _clear_settings_cache()
    assert fabric_sql.get_active_sql_source() == "offline"
    _clear_settings_cache()


def test_pg_is_reachable_ttl_cache(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_REACHABILITY_TTL_SECONDS", "300")
    _configure_pg(monkeypatch)
    _clear_settings_cache()

    fake_pg = MagicMock()
    fake_pg.is_configured.return_value = True
    fake_pg.ping.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(fabric_sql, "get_postgres_connector", lambda: fake_pg)

    assert fabric_sql.pg_is_reachable() is False
    assert fake_pg.ping.call_count == 1
    # TTL cache — second call must not ping again.
    assert fabric_sql.pg_is_reachable() is False
    assert fake_pg.ping.call_count == 1
    _clear_settings_cache()


def test_run_sql_dispatches_to_postgres_and_tags_source(temp_storage, monkeypatch):
    _configure_pg(monkeypatch)
    _clear_settings_cache()

    fake_pg = MagicMock()
    fake_pg.execute_read_only.return_value = {"rows": [{"n": 1}], "columns": ["n"]}
    monkeypatch.setattr(fabric_sql, "get_postgres_connector", lambda: fake_pg)

    result = fabric_sql.run_sql("SELECT 1 AS n", mode="explore", max_rows=5, source="postgres")
    assert result["source"] == "postgres"
    assert result["rows"] == [{"n": 1}]
    fake_pg.execute_read_only.assert_called_once_with("SELECT 1 AS n", mode="explore", max_rows=5)
    # A successful query marks the replica reachable — next check hits no ping.
    fake_pg.ping.assert_not_called()
    assert fabric_sql.pg_is_reachable() is True
    fake_pg.ping.assert_not_called()
    _clear_settings_cache()


def test_run_sql_postgres_failure_marks_unreachable(temp_storage, monkeypatch):
    _configure_pg(monkeypatch)
    monkeypatch.setenv("FABRIC_REACHABILITY_TTL_SECONDS", "300")
    _clear_settings_cache()

    fake_pg = MagicMock()
    fake_pg.execute_read_only.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(fabric_sql, "get_postgres_connector", lambda: fake_pg)

    with pytest.raises(RuntimeError):
        fabric_sql.run_sql("SELECT 1", source="postgres")

    # The failed attempt cached unreachable — pg_is_reachable must not re-ping.
    fake_pg.ping.reset_mock()
    assert fabric_sql.pg_is_reachable() is False
    fake_pg.ping.assert_not_called()
    _clear_settings_cache()


def test_run_sql_defaults_to_fabric(temp_storage, monkeypatch):
    def fake_run_fabric_sql(sql, *, mode="explore", max_rows=None):
        return {"rows": [{"n": 2}], "columns": ["n"]}

    monkeypatch.setattr(fabric_sql, "run_fabric_sql", fake_run_fabric_sql)
    result = fabric_sql.run_sql("SELECT 2 AS n")
    assert result["source"] == "fabric"
    assert result["rows"] == [{"n": 2}]


def test_estimate_row_count_for_source_postgres(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_ROW_COUNT_THRESHOLD", "50000")
    _clear_settings_cache()

    def fake_run_sql(sql, *, mode="explore", max_rows=None, source="fabric"):
        assert source == "postgres"
        assert "COUNT(*)" in sql.upper()
        return {"rows": [{"cnt": 7}], "columns": ["cnt"]}

    monkeypatch.setattr(fabric_sql, "run_sql", fake_run_sql)
    n = fabric_sql.estimate_row_count_for_source("SELECT a FROM t", "postgres")
    assert n == 7
    _clear_settings_cache()


def test_enforce_row_count_threshold_for_source_raises(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_ROW_COUNT_THRESHOLD", "100")
    _clear_settings_cache()
    monkeypatch.setattr(
        fabric_sql, "estimate_row_count_for_source", lambda sql, source, settings=None: 500
    )
    with pytest.raises(fabric_sql.RowCountExceeded) as ei:
        fabric_sql.enforce_row_count_threshold_for_source("SELECT * FROM big", "postgres")
    assert ei.value.estimated == 500
    _clear_settings_cache()


def test_get_fabric_schema_text_falls_back_to_postgres_when_fabric_down(temp_storage, monkeypatch):
    _configure_fabric(monkeypatch)
    _configure_pg(monkeypatch)
    _clear_settings_cache()

    fake_fabric = MagicMock()
    fake_fabric.is_configured.return_value = True
    fake_fabric.ping.side_effect = FabricConnectionError("down", "ล่ม")
    monkeypatch.setattr(fabric_sql, "get_fabric_connector", lambda: fake_fabric)

    fake_pg = MagicMock()
    fake_pg.is_configured.return_value = True
    fake_pg.ping.return_value = {"connected": True}
    fake_pg.fetch_schema_summary.return_value = [
        {"table_schema": "public", "table_name": "vbrk", "table_type": "BASE TABLE"}
    ]
    monkeypatch.setattr(fabric_sql, "get_postgres_connector", lambda: fake_pg)

    text = fabric_sql.get_fabric_schema_text()
    assert "vbrk" in text.lower()
    assert not text.startswith("(Fabric")
    _clear_settings_cache()


def test_get_fabric_schema_text_offline_message_when_both_unconfigured(temp_storage, monkeypatch):
    _blank_both_sources(monkeypatch)
    _clear_settings_cache()
    text = fabric_sql.get_fabric_schema_text()
    assert "Fabric not configured" in text
    _clear_settings_cache()
