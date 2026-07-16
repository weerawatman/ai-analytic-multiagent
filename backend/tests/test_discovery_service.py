"""Tests for discovery service — schema context pack and relationship heuristics."""

import json

import pytest

from backend.app.services import discovery_service


def test_detect_relationships_shared_keys():
    profiles = [
        {
            "table": "dbo.Orders",
            "columns": [{"COLUMN_NAME": "KUNNR"}, {"COLUMN_NAME": "AMOUNT"}],
        },
        {
            "table": "dbo.Customers",
            "columns": [{"COLUMN_NAME": "KUNNR"}, {"COLUMN_NAME": "NAME"}],
        },
    ]
    rels = discovery_service._detect_relationships(profiles)
    assert any(r["column"] == "KUNNR" for r in rels)
    assert len(rels[0]["tables"]) >= 2


def test_format_schema_context_pack_from_cache(temp_storage, monkeypatch):
    theme_id = "sales-theme"
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True)
    payload = {
        "theme_id": theme_id,
        "profiles": [
            {
                "table": "SAPHANADB.VBRK_All_Cleaned",
                "row_count": 1000,
                "columns": [
                    {"COLUMN_NAME": "FKDAT", "DATA_TYPE": "date"},
                    {"COLUMN_NAME": "NETWR", "DATA_TYPE": "decimal"},
                ],
                "date_columns": ["FKDAT"],
            }
        ],
        "relationships": [],
    }
    (discovery_dir / "discovery.json").write_text(json.dumps(payload), encoding="utf-8")

    text = discovery_service.format_schema_context_pack(theme_id)
    assert "VBRK_All_Cleaned" in text
    assert "FKDAT" in text
    assert "NETWR" in text


def test_get_columns_for_table(temp_storage):
    theme_id = "t1"
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True)
    payload = {
        "profiles": [
            {
                "table": "dbo.Sales",
                "columns": [{"COLUMN_NAME": "ID"}, {"COLUMN_NAME": "AMT"}],
            }
        ]
    }
    (discovery_dir / "discovery.json").write_text(json.dumps(payload), encoding="utf-8")

    cols = discovery_service.get_columns_for_table(theme_id, "dbo.Sales")
    assert cols == ["ID", "AMT"]
