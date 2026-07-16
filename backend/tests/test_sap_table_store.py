"""Tests for SAP table description store."""

import csv
from pathlib import Path

import pytest

from backend.app.services import sap_table_store


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sap_tables.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["TABNAME", "DDLANGUAGE", "DDTEXT"])
        writer.writeheader()
        writer.writerow(
            {"TABNAME": "VBRK", "DDLANGUAGE": "E", "DDTEXT": "Billing Document: Header Data"}
        )
        writer.writerow(
            {"TABNAME": "KNA1", "DDLANGUAGE": "E", "DDTEXT": "General Data in Customer Master"}
        )
        writer.writerow(
            {"TABNAME": "MARA", "DDLANGUAGE": "T", "DDTEXT": "Thai only row"}
        )
    return path


def test_import_and_lookup(sample_csv: Path, temp_storage):
    result = sap_table_store.import_from_csv(sample_csv, language="E")
    assert result["imported"] == 2
    assert result["skipped"] == 1

    desc = sap_table_store.lookup_description("VBRK")
    assert desc == "Billing Document: Header Data"


def test_tabname_candidates_fabric_cleaned():
    candidates = sap_table_store.tabname_candidates("SAPHANADB.VBRK_All_Cleaned")
    assert "VBRK_ALL_CLEANED" in candidates
    assert "VBRK" in candidates


def test_lookup_for_table_ref_cleaned_suffix(sample_csv: Path, temp_storage):
    sap_table_store.import_from_csv(sample_csv, language="E")
    match = sap_table_store.lookup_for_table_ref("SAPHANADB.VBRK_All_Cleaned")
    assert match is not None
    assert match["sap_tabname"] == "VBRK"
    assert "Billing" in match["description"]


def test_format_sap_tables_context(sample_csv: Path, temp_storage):
    sap_table_store.import_from_csv(sample_csv, language="E")
    text = sap_table_store.format_sap_tables_context(
        ["SAPHANADB.VBRK_All_Cleaned", "dbo.Dim_KNA1_Cleaned"]
    )
    assert "SAP Table Descriptions" in text
    assert "VBRK" in text
    assert "KNA1" in text
