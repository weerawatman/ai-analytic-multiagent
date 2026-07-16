"""Phase B feedback parity — status filter, upsert, DS routing, DE prompt slot."""

from __future__ import annotations

import pytest

from backend.app.agents import data_engineer
from backend.app.agents.state import AgentState
from backend.app.services import feedback_router, knowledge_store


@pytest.mark.anyio
async def test_ds_feedback_to_glossary_quality(temp_storage):
    applied = await feedback_router.apply_feedback(
        "t1",
        role="data_scientist",
        action="approve",
        comment="คอลัมน์ NetWR มี outlier บ่อย",
        theme_name="sales",
    )
    assert any(a.startswith("glossary:quality.") for a in applied["applied"])
    items = await knowledge_store.list_items("glossary", theme="sales")
    hit = next(i for i in items if i["field_key"].startswith("quality."))
    assert hit["source"] == "ceo_feedback"
    assert hit["status"] == "approved"


@pytest.mark.anyio
async def test_upsert_dedup_updates_same_key(temp_storage):
    await knowledge_store.upsert_item(
        "glossary",
        {
            "field_key": "metric.sales",
            "definition_th": "v1",
            "theme": "sales",
            "status": "draft",
            "source": "ceo_feedback",
        },
    )
    await knowledge_store.upsert_item(
        "glossary",
        {
            "field_key": "metric.sales",
            "definition_th": "v2 updated",
            "theme": "sales",
            "status": "draft",
            "source": "ceo_feedback",
        },
    )
    items = await knowledge_store.list_items("glossary", theme="sales")
    matches = [i for i in items if i["field_key"] == "metric.sales"]
    assert len(matches) == 1
    assert matches[0]["definition_th"] == "v2 updated"
    assert matches[0]["updated_at"]


@pytest.mark.anyio
async def test_reject_hidden_from_prompt_manual_draft_visible(temp_storage):
    await knowledge_store.upsert_item(
        "glossary",
        {
            "field_key": "bad.metric",
            "definition_th": "ผิด",
            "theme": "sales",
            "status": "rejected",
            "source": "ceo_feedback",
        },
    )
    await knowledge_store.add_item(
        "glossary",
        {
            "field_key": "manual.metric",
            "definition_th": "ผู้ใช้เพิ่มเอง",
            "theme": "sales",
        },
    )
    await knowledge_store.upsert_item(
        "glossary",
        {
            "field_key": "ok.metric",
            "definition_th": "ผ่าน",
            "theme": "sales",
            "status": "approved",
            "source": "ceo_feedback",
        },
    )
    await knowledge_store.upsert_item(
        "glossary",
        {
            "field_key": "consultant.metric",
            "definition_th": "จากที่ปรึกษา",
            "theme": "sales",
            "status": "draft",
            "source": "consultant",
        },
    )

    text = knowledge_store.format_knowledge_context(theme="sales")
    assert "bad.metric" not in text
    assert "manual.metric" in text
    assert "ok.metric" in text
    assert "consultant.metric" not in text

    items = await knowledge_store.list_items("glossary", theme="sales")
    cid = next(i["id"] for i in items if i["field_key"] == "consultant.metric")
    await knowledge_store.update_item("glossary", cid, {"status": "approved"})
    text2 = knowledge_store.format_knowledge_context(theme="sales")
    assert "consultant.metric" in text2


def test_de_system_prompt_has_ceo_feedback_slot():
    assert "{ceo_feedback_context}" in data_engineer.SYSTEM_PROMPT
    rendered = data_engineer.SYSTEM_PROMPT.format(
        skill="skill",
        theme="sales",
        db_schema="schema",
        discovery_context="disc",
        knowledge_context="know",
        sql_reference_context="sql",
        team_memory_context="team",
        ceo_feedback_context="CEO said use CE1SATG",
        semantic_layer="{}",
    )
    assert "CEO said use CE1SATG" in rendered


@pytest.mark.anyio
async def test_de_context_includes_ceo_feedback(temp_storage, monkeypatch):
    captured: list[str] = []

    class FakeLLM:
        async def ainvoke(self, prompt):
            captured.append(prompt if isinstance(prompt, str) else str(prompt))

            class R:
                content = "DE summary"

            return R()

    monkeypatch.setattr(
        "backend.app.core.llm.make_chat_ollama", lambda temperature=0: FakeLLM()
    )
    from backend.app.agents.context_nodes import de_context_node
    from langchain_core.messages import HumanMessage

    state = AgentState(
        messages=[HumanMessage(content="ยอดขาย")],
        theme="sales",
        ceo_feedback_context="ใช้ CE1SATG ไม่ใช่ VBRK",
        discovery_context="disc",
    )
    result = await de_context_node(state)
    assert captured
    assert "ใช้ CE1SATG ไม่ใช่ VBRK" in captured[0]
    assert result["schema_info"]
