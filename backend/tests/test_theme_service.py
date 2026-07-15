from backend.app.services.theme_service import (
    _heuristic_themes,
    cluster_schema_rows,
    get_themes,
    save_cached_themes,
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
