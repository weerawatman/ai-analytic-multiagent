"""Tests for WH_Silver SQL reference loader."""

import json
from pathlib import Path

from backend.app.services import sql_reference_store


def test_parse_ddl_columns():
    ddl = """CREATE TABLE [SAPHANADB].[VBRK_All_Cleaned] (
    [Billing_Date] varchar(255) NULL,
    [Net_Value_In_Document_Currency] decimal(38,10) NULL
);"""
    cols = sql_reference_store._parse_ddl_columns(ddl)
    assert "Billing_Date" in cols
    assert "Net_Value_In_Document_Currency" in cols


def test_format_sql_reference_for_sales_theme(temp_storage, monkeypatch):
    sql_root = temp_storage / "knowledge" / "sql_reference"
    tables_dir = sql_root / "SAPHANADB" / "Tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    ddl_path = tables_dir / "VBRK_All_Cleaned.sql"
    ddl_path.write_text(
        "CREATE TABLE [SAPHANADB].[VBRK_All_Cleaned] (\n"
        "  [Billing_Date] varchar(255) NULL,\n"
        "  [Net_Value_In_Document_Currency] decimal(38,10) NULL\n);",
        encoding="utf-8",
    )
    manifest = {
        "version": "1.0",
        "items": [
            {
                "id": "vbrk",
                "table_ref": "SAPHANADB.VBRK_All_Cleaned",
                "file_path": "SAPHANADB/Tables/VBRK_All_Cleaned.sql",
                "kind": "table_ddl",
                "description_th": "Billing header",
            }
        ],
    }
    (sql_root / "_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    text = sql_reference_store.format_sql_reference_context(
        ["SAPHANADB.VBRK_All_Cleaned"]
    )
    assert "WH_Silver SQL Reference" in text
    assert "Billing_Date" in text
    assert "Net_Value_In_Document_Currency" in text


def test_get_table_refs_for_theme_sales(temp_storage, monkeypatch):
    themes_dir = temp_storage / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    cached = {
        "themes": [
            {
                "id": "sales",
                "sample_tables": ["SAPHANADB.VBRK_All_Cleaned"],
            }
        ]
    }
    (themes_dir / "cached_themes.json").write_text(json.dumps(cached), encoding="utf-8")

    refs = sql_reference_store.get_table_refs_for_theme("sales")
    assert refs == ["SAPHANADB.VBRK_All_Cleaned"]
