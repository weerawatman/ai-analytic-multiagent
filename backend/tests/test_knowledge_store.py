"""Tests for knowledge store CRUD."""

import pytest

from backend.app.services import knowledge_store


@pytest.mark.anyio
async def test_add_and_list_glossary(temp_storage):
    item = await knowledge_store.add_item(
        "glossary",
        {
            "field_key": "VBRK.FKDAT",
            "definition_th": "วันที่ billing",
            "theme": "ยอดขาย",
        },
    )
    assert item["id"]
    assert item["status"] == "draft"

    items = await knowledge_store.list_items("glossary", theme="ยอดขาย")
    assert any(i["field_key"] == "VBRK.FKDAT" for i in items)


@pytest.mark.anyio
async def test_approve_glossary_item(temp_storage):
    created = await knowledge_store.add_item(
        "glossary",
        {"field_key": "VBRK.NETWR", "definition_th": "ยอดขายสุทธิ"},
    )
    updated = await knowledge_store.update_item(
        "glossary", created["id"], {"status": "approved"}
    )
    assert updated["status"] == "approved"


def test_format_knowledge_context(temp_storage):
    import asyncio

    asyncio.run(
        knowledge_store.add_item(
            "glossary",
            {"field_key": "SALES", "definition_th": "ยอดขาย", "theme": "sales"},
        )
    )
    text = knowledge_store.format_knowledge_context(theme="sales")
    assert "SALES" in text
    assert "ยอดขาย" in text
