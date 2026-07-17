"""Phase F — Fabric vs Postgres mirror parity comparison logic.

Covers the two real issues found in the Phase F deep audit: NAMEDATALEN
63-char silent truncation (CE1SATG) and intentional numeric-cast type
differences (VBRK money/rate columns) — plus generic drift detection.
"""

from __future__ import annotations

from backend.app.services.schema_parity import (
    PG_NAMEDATALEN,
    build_parity_report,
    compare_columns,
    find_overlong_names,
    normalize_type,
)

# The exact truncation case found live: 67-char SAP name cut to 63 on PG.
_LONG_NAME = "Document_Number_Of_Line_Item_In_Profitability_Analysis_BELNR_SENDER"


def _cols(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"column_name": n, "data_type": t} for n, t in pairs]


def test_normalize_type_bridges_dialect_names():
    assert normalize_type("varchar") == normalize_type("character varying")
    assert normalize_type("decimal") == normalize_type("numeric")
    assert normalize_type("datetime2") == normalize_type("timestamp without time zone")
    assert normalize_type("varchar") != normalize_type("numeric")


def test_find_overlong_names_flags_over_63_chars():
    assert find_overlong_names([_LONG_NAME, "Billing_Document"]) == [_LONG_NAME]
    assert find_overlong_names(["x" * PG_NAMEDATALEN]) == []
    assert find_overlong_names(["x" * (PG_NAMEDATALEN + 1)]) == ["x" * 64]


def test_compare_columns_identical():
    cols = _cols(("Billing_Document", "varchar"), ("Billing_Date", "date"))
    report = compare_columns(cols, cols)
    assert report["matched"] == 2
    assert not report["missing_in_pg"]
    assert not report["extra_in_pg"]
    assert not report["truncation_suspects"]
    assert not report["type_diffs"]


def test_compare_columns_detects_namedatalen_truncation():
    """Fabric has the 67-char name; PG silently truncated it at 63 — this must
    be reported as a truncation suspect, not as generic missing+extra noise."""
    fabric = _cols((_LONG_NAME, "varchar"))
    pg = _cols((_LONG_NAME[:PG_NAMEDATALEN], "character varying"))
    report = compare_columns(fabric, pg)
    assert report["truncation_suspects"] == [
        {"fabric": _LONG_NAME, "postgres": _LONG_NAME[:PG_NAMEDATALEN]}
    ]
    assert report["missing_in_pg"] == []
    assert report["extra_in_pg"] == []
    assert report["overlong_fabric_names"] == [_LONG_NAME]


def test_compare_columns_type_diff_is_informational():
    """VBRK pattern: Fabric says varchar, mirror cast to numeric — reported as
    a type diff, not a name mismatch."""
    fabric = _cols(("Net_Value_In_Document_Currency", "varchar"))
    pg = _cols(("Net_Value_In_Document_Currency", "numeric"))
    report = compare_columns(fabric, pg)
    assert report["type_diffs"] == [
        {
            "column": "Net_Value_In_Document_Currency",
            "fabric": "varchar",
            "postgres": "numeric",
        }
    ]
    assert not report["missing_in_pg"] and not report["extra_in_pg"]


def test_compare_columns_varchar_vs_character_varying_is_not_a_diff():
    fabric = _cols(("Billing_Document", "varchar"))
    pg = _cols(("Billing_Document", "character varying"))
    assert compare_columns(fabric, pg)["type_diffs"] == []


def test_compare_columns_real_drift():
    fabric = _cols(("A", "varchar"), ("B", "varchar"))
    pg = _cols(("A", "character varying"), ("C", "character varying"))
    report = compare_columns(fabric, pg)
    assert report["missing_in_pg"] == ["B"]
    assert report["extra_in_pg"] == ["C"]


def test_build_parity_report_statuses():
    fabric = {
        "OK_TABLE": {"columns": _cols(("A", "varchar")), "row_count": 10},
        "TYPE_TABLE": {"columns": _cols(("Amt", "varchar")), "row_count": 5},
        "DRIFT_TABLE": {"columns": _cols(("X", "varchar")), "row_count": 3},
        "FABRIC_ONLY": {"columns": _cols(("Z", "varchar")), "row_count": 1},
    }
    pg = {
        "OK_TABLE": {"columns": _cols(("A", "character varying")), "row_count": 10},
        "TYPE_TABLE": {"columns": _cols(("Amt", "numeric")), "row_count": 5},
        "DRIFT_TABLE": {"columns": _cols(("Y", "character varying")), "row_count": 3},
        "PG_ONLY": {"columns": _cols(("W", "character varying")), "row_count": 1},
    }
    report = build_parity_report(fabric, pg)
    assert report["tables"]["OK_TABLE"]["status"] == "ok"
    assert report["tables"]["TYPE_TABLE"]["status"] == "type_diff"
    assert report["tables"]["DRIFT_TABLE"]["status"] == "mismatch"
    assert report["tables"]["FABRIC_ONLY"]["status"] == "missing_in_pg"
    assert report["tables"]["PG_ONLY"]["status"] == "missing_in_fabric"
    assert report["total"] == 5
    assert report["ok"] == 1
    assert report["type_diff_only"] == 1
    assert set(report["drift_tables"]) == {"DRIFT_TABLE", "FABRIC_ONLY", "PG_ONLY"}
    assert report["drift"] is True


def test_build_parity_report_row_count_mismatch_is_drift():
    fabric = {"T": {"columns": _cols(("A", "varchar")), "row_count": 100}}
    pg = {"T": {"columns": _cols(("A", "character varying")), "row_count": 90}}
    report = build_parity_report(fabric, pg)
    assert report["tables"]["T"]["status"] == "mismatch"
    assert report["tables"]["T"]["row_count"]["match"] is False
    assert report["drift"] is True


def test_build_parity_report_missing_row_counts_do_not_flag_drift():
    """--skip-rowcount mode: counts are None on both sides — structure-only pass."""
    fabric = {"T": {"columns": _cols(("A", "varchar")), "row_count": None}}
    pg = {"T": {"columns": _cols(("A", "character varying")), "row_count": None}}
    report = build_parity_report(fabric, pg)
    assert report["tables"]["T"]["status"] == "ok"
    assert report["tables"]["T"]["row_count"]["match"] is None
    assert report["drift"] is False


def test_verify_pg_parity_script_importable_and_refuses_without_config(monkeypatch):
    """The CLI must exit 2 (cannot run) when live credentials are absent —
    never fabricate a result."""
    import importlib.util
    from pathlib import Path
    from unittest.mock import MagicMock

    script = Path(__file__).resolve().parents[2] / "scripts" / "verify_pg_parity.py"
    spec = importlib.util.spec_from_file_location("verify_pg_parity", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    unconfigured = MagicMock()
    unconfigured.is_configured.return_value = False
    monkeypatch.setattr(
        "backend.app.services.fabric_connector.get_fabric_connector", lambda: unconfigured
    )
    monkeypatch.setattr("sys.argv", ["verify_pg_parity.py"])
    assert module.main() == 2
