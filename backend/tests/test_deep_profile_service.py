"""Deep-profiling homework artifact — schema, persistence, evidence labels."""

from __future__ import annotations

import json

import pytest

from backend.app.services import deep_profile_service
from backend.app.services.deep_profile_service import (
    build_homework,
    classify_table_role,
    format_homework_context,
    load_homework,
)


@pytest.fixture
def theme_with_discovery(temp_storage):
    theme_id = "hwtheme"
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True, exist_ok=True)
    (discovery_dir / "discovery.json").write_text(
        json.dumps(
            {
                "theme_id": theme_id,
                "discovered_at": "2026-07-17T12:00:00+00:00",
                "database": "WH_Silver",
                "tables_profiled": 3,
                "profiles": [
                    {
                        "table": "SAPHANADB.CE1SATG_All_Cleaned",
                        "table_name": "CE1SATG_All_Cleaned",
                        "row_count": 1_636_593,
                        "columns": [
                            {"COLUMN_NAME": "SourceMonth", "DATA_TYPE": "varchar"},
                            {"COLUMN_NAME": "Revenue", "DATA_TYPE": "decimal"},
                            {"COLUMN_NAME": "COGS_Actual", "DATA_TYPE": "decimal"},
                            {"COLUMN_NAME": "Profit_Center", "DATA_TYPE": "varchar"},
                            {"COLUMN_NAME": "Sales_Amount_Text", "DATA_TYPE": "varchar"},
                        ],
                    },
                    {
                        "table": "SAPHANADB.Dim_MAKT_Cleaned",
                        "table_name": "Dim_MAKT_Cleaned",
                        "row_count": 38_059,
                        "columns": [{"COLUMN_NAME": "Material", "DATA_TYPE": "varchar"}],
                    },
                    {
                        "table": "SAPHANADB.CSKT_Cleaned",
                        "table_name": "CSKT_Cleaned",
                        "row_count": 0,
                        "columns": [{"COLUMN_NAME": "Cost_Center", "DATA_TYPE": "varchar"}],
                    },
                ],
                "relationships": [
                    {
                        "column": "PROFIT_CENTER",
                        "tables": ["SAPHANADB.CE1SATG_All_Cleaned", "SAPHANADB.CSKT_Cleaned"],
                        "confidence": "medium",
                        "note": "Shared key candidate",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return theme_id


def test_classify_table_role():
    assert classify_table_role({"table_name": "CE1SATG_All_Cleaned", "row_count": 1_000_000}) == "fact"
    assert classify_table_role({"table_name": "Dim_MARA_Cleaned", "row_count": 500_000}) == "dimension"
    assert classify_table_role({"table_name": "MAKT", "row_count": 100}) == "dimension"
    assert classify_table_role({"table_name": "CSKT_Cleaned", "row_count": 0}) == "empty"
    assert classify_table_role({"table_name": "X", "row_count": None}) == "unknown"


def test_build_homework_offline_persists_full_schema(theme_with_discovery, monkeypatch):
    """Offline build: evidence from disk cache only, artifact complete + reloadable."""
    monkeypatch.setattr(deep_profile_service, "get_active_sql_source", lambda: "offline")

    artifact = build_homework(theme_with_discovery, "Saphanadb")

    assert artifact["evidence_level"] == "disk_cache"
    assert artifact["source"] == "offline"
    assert artifact["generated_at"]
    assert artifact["discovery_freshness"] == "2026-07-17T12:00:00+00:00"
    assert artifact["table_roles"]["SAPHANADB.CE1SATG_All_Cleaned"] == "fact"
    assert artifact["table_roles"]["SAPHANADB.Dim_MAKT_Cleaned"] == "dimension"
    assert artifact["table_roles"]["SAPHANADB.CSKT_Cleaned"] == "empty"
    assert artifact["row_counts"]["SAPHANADB.CE1SATG_All_Cleaned"] == 1_636_593

    issues = {i["issue"] for i in artifact["data_quality_issues"]}
    assert "empty_table" in issues
    assert "varchar_measure_columns" in issues  # Sales_Amount_Text is varchar

    joins = artifact["join_candidates"]
    assert joins and joins[0]["needs_confirmation"] is True

    homework_roles = artifact["role_homework"]
    for role in ("data_engineer", "data_scientist", "data_analyst", "business_analyst"):
        assert role in homework_roles
    # Honesty requirement: never claim ML where there is none.
    assert "ไม่มีการเทรนโมเดล ML" in homework_roles["data_scientist"]["note_th"]

    # Persistence round-trip
    loaded = load_homework(theme_with_discovery)
    assert loaded is not None
    assert loaded["theme_id"] == theme_with_discovery
    assert loaded["table_roles"] == artifact["table_roles"]


def test_build_homework_live_collects_stats_and_ranges(theme_with_discovery, monkeypatch):
    monkeypatch.setattr(deep_profile_service, "get_active_sql_source", lambda: "fabric")

    def fake_run_sql(sql, *, mode="", max_rows=None, source="fabric"):
        if "MIN(" in sql:
            return {"rows": [{"min_value": "202401", "max_value": "202506"}], "source": source}
        return {
            "rows": [
                {"SourceMonth": "202505", "Revenue": "100.5", "COGS_Actual": None,
                 "Profit_Center": "F1132M", "Sales_Amount_Text": ""},
                {"SourceMonth": "202506", "Revenue": "200.0", "COGS_Actual": None,
                 "Profit_Center": "F1132M", "Sales_Amount_Text": ""},
            ],
            "source": source,
        }

    monkeypatch.setattr(deep_profile_service, "run_sql", fake_run_sql)

    artifact = build_homework(theme_with_discovery, "Saphanadb")
    assert artifact["evidence_level"] == "fabric_live"
    rng = artifact["date_ranges"]["SAPHANADB.CE1SATG_All_Cleaned"]
    assert rng["column"] == "SourceMonth"
    assert rng["min"] == "202401" and rng["max"] == "202506"

    stats = {s["column"]: s for s in artifact["column_stats"]["SAPHANADB.CE1SATG_All_Cleaned"]}
    assert stats["COGS_Actual"]["null_pct"] == 100.0
    assert stats["Revenue"]["is_numeric_content"] is True
    assert stats["Profit_Center"]["distinct_in_sample"] == 1
    # 100% null column must surface as a DQ issue
    assert any(
        i["issue"] == "high_null_column" and "COGS_Actual" in i["detail_th"]
        for i in artifact["data_quality_issues"]
    )


def test_build_homework_live_failure_degrades_to_cache(theme_with_discovery, monkeypatch):
    monkeypatch.setattr(deep_profile_service, "get_active_sql_source", lambda: "fabric")

    def broken_run_sql(sql, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(deep_profile_service, "run_sql", broken_run_sql)

    artifact = build_homework(theme_with_discovery, "Saphanadb")
    assert artifact["evidence_level"] == "disk_cache"
    assert artifact["live_errors"]
    # Errors are recorded as types only, never raw messages.
    assert all("boom" not in e for e in artifact["live_errors"])


def test_build_homework_requires_discovery(temp_storage):
    with pytest.raises(ValueError):
        build_homework("no-such-theme")


def test_format_homework_context(theme_with_discovery, monkeypatch):
    monkeypatch.setattr(deep_profile_service, "get_active_sql_source", lambda: "offline")
    build_homework(theme_with_discovery, "Saphanadb")
    text = format_homework_context(theme_with_discovery)
    assert "Data Homework Evidence" in text
    assert "SAPHANADB.CE1SATG_All_Cleaned" in text
    assert "fact" in text
    assert len(text) <= 2500

    assert format_homework_context("missing-theme") == ""
