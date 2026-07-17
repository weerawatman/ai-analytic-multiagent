"""Knowledge-context budgeting — metric formulas and table roles must always
reach agents; the old flat 20-item cap silently dropped owner column mappings."""

from __future__ import annotations

import asyncio

from backend.app.services import knowledge_store
from backend.app.services.knowledge_store import format_knowledge_context


def _add(kind: str, item: dict) -> None:
    asyncio.run(knowledge_store.add_item(kind, item))


def test_metrics_and_tables_survive_many_column_entries(temp_storage):
    """40+ glossary entries: metrics + tables must never be cut by columns."""
    for i in range(30):
        _add(
            "glossary",
            {
                "field_key": f"CE1SATG.VVA{i:02d}",
                "definition_th": f"คอลัมน์ส่วนประกอบที่ {i} — แมปเป็น COGS_Act_Component_{i}",
                "theme": "Saphanadb",
                "source": "owner",
            },
        )
    for key in ("metric.gross_profit", "metric.cogs_act_vc", "metric.revenue_plus_inter"):
        _add(
            "glossary",
            {
                "field_key": key,
                "definition_th": f"สูตร {key} (owner ยืนยัน)",
                "theme": "Saphanadb",
                "source": "owner",
            },
        )
    for key in ("table.CE1SATG_All_Cleaned", "table.Dim_MARA_Cleaned"):
        _add(
            "glossary",
            {
                "field_key": key,
                "definition_th": f"บทบาทตาราง {key}",
                "theme": "Saphanadb",
                "source": "owner",
            },
        )

    text = format_knowledge_context(theme="Saphanadb")
    # Metrics and table roles always present, regardless of column volume.
    assert "metric.gross_profit" in text
    assert "metric.cogs_act_vc" in text
    assert "metric.revenue_plus_inter" in text
    assert "table.CE1SATG_All_Cleaned" in text
    assert "table.Dim_MARA_Cleaned" in text
    # With 35 entries (< budget) the column mappings also all fit.
    assert "CE1SATG.VVA29" in text


def test_metrics_ordered_before_columns(temp_storage):
    _add(
        "glossary",
        {"field_key": "AAA.column_first_alphabetically", "definition_th": "คอลัมน์", "theme": "t"},
    )
    _add(
        "glossary",
        {"field_key": "metric.important", "definition_th": "สูตรสำคัญ", "theme": "t"},
    )
    text = format_knowledge_context(theme="t")
    assert text.index("metric.important") < text.index("AAA.column_first_alphabetically")


def test_oversized_glossary_notes_omissions(temp_storage):
    """When the char budget is exceeded, columns are dropped with a visible note
    — never silently, and never at the expense of metric entries."""
    for i in range(400):
        _add(
            "glossary",
            {
                "field_key": f"BIG.col_{i:03d}",
                "definition_th": "คำอธิบายยาว " * 10,
                "theme": "big",
            },
        )
    _add(
        "glossary",
        {"field_key": "metric.must_survive", "definition_th": "สูตรที่ต้องรอด", "theme": "big"},
    )
    text = format_knowledge_context(theme="big")
    assert "metric.must_survive" in text
    assert "omitted for prompt budget" in text
    assert len(text) < 15000


def test_rejected_and_machine_drafts_still_hidden(temp_storage):
    _add(
        "glossary",
        {"field_key": "metric.rejected", "definition_th": "x", "theme": "t", "status": "rejected"},
    )
    _add(
        "glossary",
        {
            "field_key": "metric.consultant_draft",
            "definition_th": "x",
            "theme": "t",
            "source": "consultant",
        },
    )
    _add("glossary", {"field_key": "metric.visible", "definition_th": "x", "theme": "t"})
    text = format_knowledge_context(theme="t")
    assert "metric.rejected" not in text
    assert "metric.consultant_draft" not in text
    assert "metric.visible" in text


def test_empty_store_message(temp_storage):
    assert format_knowledge_context(theme="none") == "(no knowledge entries yet)"
