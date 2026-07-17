from unittest.mock import MagicMock

import pytest

from backend.app.services import theme_service
from backend.app.services.fabric_connector import FabricConnectionError
from backend.app.services.theme_service import (
    _heuristic_themes,
    cluster_schema_rows,
    get_themes,
    save_cached_themes,
    scan_themes,
)


def test_cluster_schema_rows_groups_sales() -> None:
    rows = [
        {"table_schema": "dbo", "table_name": "sales_order", "table_type": "BASE TABLE"},
        {"table_schema": "dbo", "table_name": "customer_master", "table_type": "BASE TABLE"},
        {"table_schema": "dbo", "table_name": "random_xyz", "table_type": "BASE TABLE"},
    ]
    clusters = cluster_schema_rows(rows)
    assert "sales" in clusters
    assert len(clusters["sales"]) == 2


def test_heuristic_themes_returns_three() -> None:
    rows = [
        {"table_schema": "dbo", "table_name": f"sales_{i}", "table_type": "BASE TABLE"}
        for i in range(5)
    ] + [
        {"table_schema": "dbo", "table_name": f"stock_{i}", "table_type": "BASE TABLE"}
        for i in range(3)
    ]
    clusters = cluster_schema_rows(rows)
    themes = _heuristic_themes(clusters, limit=3)
    assert len(themes) == 3
    assert themes[0]["table_count"] >= themes[1]["table_count"]
    assert len(themes[0]["starter_questions_th"]) >= 2


def test_save_and_load_cached_themes(temp_storage) -> None:
    payload = {
        "scanned_at": "2026-01-01T00:00:00Z",
        "themes": [{"id": "sales", "name_th": "ยอดขาย", "rationale_th": "r", "starter_questions_th": ["q1"]}],
    }
    save_cached_themes(payload)
    loaded = get_themes()
    assert loaded["themes"][0]["id"] == "sales"


SCHEMA_ROWS = [
    {"table_schema": "SAPHANADB", "table_name": f"sales_{i}", "table_type": "BASE TABLE"}
    for i in range(5)
]


async def test_scan_falls_back_to_postgres_when_fabric_down(temp_storage, monkeypatch) -> None:
    """Phase F: Fabric paused -> scan must use the Postgres WH_Silver mirror."""
    monkeypatch.setattr(theme_service, "fabric_can_query", lambda: False)
    monkeypatch.setattr(theme_service, "pg_can_query", lambda: True)

    fake_pg = MagicMock()
    fake_pg.is_configured.return_value = True
    fake_pg.fetch_schema_summary.return_value = SCHEMA_ROWS
    fake_pg.settings.pg_replica_db = "WH_Silver"
    monkeypatch.setattr(theme_service, "get_postgres_connector", lambda: fake_pg)

    fake_fabric = MagicMock()
    fake_fabric.is_configured.return_value = True
    monkeypatch.setattr(theme_service, "get_fabric_connector", lambda: fake_fabric)

    result = await scan_themes(use_llm=False)
    assert result["source"] == "postgres"
    assert result["database"] == "WH_Silver"
    assert result["total_tables_scanned"] == 5
    assert len(result["themes"]) == 3
    assert "Postgres" in result["message"]
    fake_fabric.fetch_schema_summary.assert_not_called()


async def test_scan_reuses_cache_when_all_sources_down(temp_storage, monkeypatch) -> None:
    """Fabric paused + no Postgres -> return cached themes with Thai warning, not 500."""
    save_cached_themes(
        {
            "scanned_at": "2026-01-01T00:00:00Z",
            "themes": [
                {"id": "sales", "name_th": "ยอดขาย", "rationale_th": "r", "starter_questions_th": ["q1"]}
            ],
        }
    )
    monkeypatch.setattr(theme_service, "fabric_can_query", lambda: False)
    monkeypatch.setattr(theme_service, "pg_can_query", lambda: False)

    fake = MagicMock()
    fake.is_configured.return_value = True
    monkeypatch.setattr(theme_service, "get_fabric_connector", lambda: fake)
    monkeypatch.setattr(theme_service, "get_postgres_connector", lambda: fake)

    result = await scan_themes(use_llm=True)
    assert result["source"] == "cache"
    assert result["themes"][0]["id"] == "sales"
    assert "cache" in result["message"] or "ดิสก์" in result["message"]


async def test_scan_raises_503_error_when_all_down_and_no_cache(temp_storage, monkeypatch) -> None:
    monkeypatch.setattr(theme_service, "fabric_can_query", lambda: False)
    monkeypatch.setattr(theme_service, "pg_can_query", lambda: False)

    fake = MagicMock()
    fake.is_configured.return_value = True
    monkeypatch.setattr(theme_service, "get_fabric_connector", lambda: fake)
    monkeypatch.setattr(theme_service, "get_postgres_connector", lambda: fake)

    with pytest.raises(FabricConnectionError):
        await scan_themes(use_llm=False)


async def test_scan_fabric_error_falls_through_to_postgres(temp_storage, monkeypatch) -> None:
    """Fabric passes the reachability gate but the query still fails (e.g. pause mid-flight)."""
    monkeypatch.setattr(theme_service, "fabric_can_query", lambda: True)
    monkeypatch.setattr(theme_service, "pg_can_query", lambda: True)
    monkeypatch.setattr(theme_service, "mark_fabric_unreachable", lambda: None)

    fake_fabric = MagicMock()
    fake_fabric.is_configured.return_value = True
    fake_fabric.fetch_schema_summary.side_effect = FabricConnectionError("paused", "pause")
    monkeypatch.setattr(theme_service, "get_fabric_connector", lambda: fake_fabric)

    fake_pg = MagicMock()
    fake_pg.is_configured.return_value = True
    fake_pg.fetch_schema_summary.return_value = SCHEMA_ROWS
    fake_pg.settings.pg_replica_db = "WH_Silver"
    monkeypatch.setattr(theme_service, "get_postgres_connector", lambda: fake_pg)

    result = await scan_themes(use_llm=False)
    assert result["source"] == "postgres"
