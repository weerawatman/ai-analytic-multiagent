"""Insight starter pack — formula parsing, hypothesis vs validated labels."""

from __future__ import annotations

import json

import pytest

from backend.app.services import insight_starter_service
from backend.app.services.insight_starter_service import (
    build_starter_pack,
    load_starter_pack,
    parse_cleaned_expression,
)

_CE1SATG_COLUMNS = {
    "SourceMonth",
    "Revenue",
    "Inter_Company",
    "Return_Revenue",
    "COGS_Actual",
    "Profit_Center",
}


def test_parse_cleaned_expression_valid():
    definition = (
        "Revenue +Inter = KFG0002 (owner ยืนยัน) = VVR06 + ERLOS + VVR01 | "
        "Fabric cleaned: Inter_Company + Revenue + Return_Revenue | SQL: SUM(...)"
    )
    expr = parse_cleaned_expression(definition, _CE1SATG_COLUMNS)
    assert expr == "Inter_Company + Revenue + Return_Revenue"


def test_parse_cleaned_expression_with_parens_and_trailing_thai():
    definition = (
        "Gross Profit = KFG0002 - VVA01 | Fabric cleaned: "
        "(Inter_Company + Revenue + Return_Revenue) - COGS_Actual. หมายเหตุ: ..."
    )
    expr = parse_cleaned_expression(definition, _CE1SATG_COLUMNS)
    assert expr == "(Inter_Company + Revenue + Return_Revenue) - COGS_Actual"


def test_parse_cleaned_expression_rejects_unknown_columns():
    definition = "X | Fabric cleaned: Not_A_Column + Revenue"
    assert parse_cleaned_expression(definition, _CE1SATG_COLUMNS) is None


def test_parse_cleaned_expression_no_marker():
    assert parse_cleaned_expression("นิยามทั่วไป ไม่มีสูตร", _CE1SATG_COLUMNS) is None


@pytest.fixture
def theme_ready(temp_storage):
    """Discovery + owner metric glossary for a CE1SATG-style theme."""
    theme_id = "sp-theme"
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True, exist_ok=True)
    (discovery_dir / "discovery.json").write_text(
        json.dumps(
            {
                "theme_id": theme_id,
                "discovered_at": "2026-07-17T12:00:00+00:00",
                "profiles": [
                    {
                        "table": "SAPHANADB.CE1SATG_All_Cleaned",
                        "table_name": "CE1SATG_All_Cleaned",
                        "row_count": 1_636_593,
                        "columns": [{"COLUMN_NAME": c, "DATA_TYPE": "decimal"} for c in _CE1SATG_COLUMNS],
                    }
                ],
                "relationships": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    glossary = {
        "version": "1.0",
        "items": [
            {
                "id": "1",
                "status": "draft",
                "source": "owner",
                "theme": "Saphanadb",
                "field_key": "metric.revenue_plus_inter",
                "definition_th": "Revenue +Inter | Fabric cleaned: Inter_Company + Revenue + Return_Revenue | SQL: ...",
            },
            {
                "id": "2",
                "status": "draft",
                "source": "owner",
                "theme": "Saphanadb",
                "field_key": "metric.gross_profit",
                "definition_th": (
                    "Gross Profit | Fabric cleaned: "
                    "(Inter_Company + Revenue + Return_Revenue) - COGS_Actual. หมายเหตุ"
                ),
            },
        ],
    }
    (temp_storage / "knowledge" / "glossary.json").write_text(
        json.dumps(glossary, ensure_ascii=False), encoding="utf-8"
    )
    return theme_id


def test_starter_pack_offline_items_are_hypotheses(theme_ready, monkeypatch):
    monkeypatch.setattr(insight_starter_service, "get_active_sql_source", lambda: "offline")

    pack = build_starter_pack(theme_ready, "Saphanadb")
    items = pack["items"]
    assert 3 <= len(items) <= 5
    # Nothing executed offline — everything stays an explicit hypothesis.
    assert all(i["evidence_status"] == "not_run" for i in items)
    for item in items:
        assert item["hypothesis_th"]
        assert item["sql"]
        assert item["fields_needed"]
        assert item["expected_decision_th"]
        assert item["confidence"] in ("high", "medium", "low")
    # Persistence round-trip
    loaded = load_starter_pack(theme_ready)
    assert loaded and len(loaded["items"]) == len(items)
    assert "สมมติฐาน" in pack["method_note_th"]


def test_starter_pack_baseline_validated_with_aggregate_rows(theme_ready, monkeypatch):
    monkeypatch.setattr(insight_starter_service, "get_active_sql_source", lambda: "fabric")

    executed_sql: list[str] = []

    def fake_run_sql(sql, *, mode="", max_rows=None, source="fabric"):
        executed_sql.append(sql)
        if "MAX(" in sql:
            return {"rows": [{"max_month": "202506"}], "source": source}
        return {
            "rows": [
                {"SourceMonth": "202501", "revenue_plus_inter": 100, "cogs_actual": 60, "gross_profit": 40},
                {"SourceMonth": "202502", "revenue_plus_inter": 120, "cogs_actual": 70, "gross_profit": 50},
            ],
            "source": source,
        }

    monkeypatch.setattr(insight_starter_service, "run_sql", fake_run_sql)

    pack = build_starter_pack(theme_ready, "Saphanadb")
    baseline = pack["items"][0]
    assert baseline["id"] == "baseline_trend_6m"
    assert baseline["evidence_status"] == "validated"
    assert baseline["executed_source"] == "fabric"
    assert baseline["result_rows"]  # aggregates only
    assert "{cutoff}" not in baseline["executed_sql"]
    assert "202501" in baseline["executed_sql"]  # 202506 - 5 months
    # Only the baseline ran — the rest remain hypotheses.
    assert all(i["evidence_status"] == "not_run" for i in pack["items"][1:])
    # Read-only shape: single SELECT statements only.
    assert all(s.lstrip().upper().startswith("SELECT") for s in executed_sql)


def test_starter_pack_baseline_failure_is_labeled(theme_ready, monkeypatch):
    monkeypatch.setattr(insight_starter_service, "get_active_sql_source", lambda: "fabric")

    def broken_run_sql(sql, **kwargs):
        if "MAX(" in sql:
            return {"rows": [{"max_month": "202506"}]}
        raise RuntimeError("db down")

    monkeypatch.setattr(insight_starter_service, "run_sql", broken_run_sql)

    pack = build_starter_pack(theme_ready, "Saphanadb")
    baseline = pack["items"][0]
    assert baseline["evidence_status"] == "failed"
    assert "db down" not in json.dumps(pack)  # no raw error leakage


def test_starter_pack_without_metrics_notes_reason(temp_storage, monkeypatch):
    theme_id = "no-metrics"
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True, exist_ok=True)
    (discovery_dir / "discovery.json").write_text(
        json.dumps(
            {
                "theme_id": theme_id,
                "profiles": [
                    {
                        "table": "S.T",
                        "table_name": "T",
                        "row_count": 500_000,
                        "columns": [{"COLUMN_NAME": "SourceMonth", "DATA_TYPE": "varchar"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(insight_starter_service, "get_active_sql_source", lambda: "offline")
    pack = build_starter_pack(theme_id, "อื่นๆ")
    assert pack["items"] == []
    assert pack["note_th"]
