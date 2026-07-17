"""Phase F — provenance labels + dialect-portable CAST guidance.

The CEO must always see which source produced an answer (Fabric / Postgres
fallback / offline) — no silent fallback that could pass off older mirror data
as live Fabric data. And the DA prompt must carry the CAST rule for both
dialects, since most WH_Silver columns are varchar even when they hold numbers.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from backend.app.agents.data_analyst import _CAST_GUIDANCE, _DIALECT_RULES, _dialect_rules_for
from backend.app.agents.orchestrator import summarize_node
from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.services import quality_assembly
from backend.app.services.backlog_store import create_item
from backend.app.services.quality_assembly import (
    build_quality_payload,
    data_source_label_th,
    format_explore_response_th,
)


# ── CAST guidance ────────────────────────────────────────────────────────────


def test_cast_guidance_present_in_both_dialect_rules():
    assert "CAST(col AS DECIMAL(18,2))" in _CAST_GUIDANCE
    for source in ("fabric", "postgres"):
        assert "CAST(col AS DECIMAL(18,2))" in _DIALECT_RULES[source]
        assert "implicit" in _DIALECT_RULES[source]


def test_cast_guidance_in_data_analyst_skill():
    skill = load_agent_skill("data_analyst")
    assert "CAST(col AS DECIMAL(18,2))" in skill
    assert "varchar" in skill


def test_dialect_rules_for_unknown_source_defaults_to_fabric():
    assert _dialect_rules_for("offline") == _DIALECT_RULES["fabric"]


# ── Provenance labels ────────────────────────────────────────────────────────


def test_data_source_labels_cover_all_sources():
    assert "หลัก" in data_source_label_th("fabric")
    assert "สำรอง" in data_source_label_th("postgres")
    assert "Offline" in data_source_label_th("offline")
    # Unknown/empty degrades to the offline label — never a KeyError.
    assert data_source_label_th("") == data_source_label_th("offline")


def _explore_state(**kwargs) -> AgentState:
    base = dict(
        thread_id="t-prov",
        mode="explore",
        theme="sales",
        messages=[HumanMessage(content="ยอดขาย?")],
        generated_sql="SELECT 1 AS n",
        query_result="SQL: SELECT 1 AS n\nANALYSIS: โต\nASSUMPTIONS:\n- daily",
    )
    base.update(kwargs)
    return AgentState(**base)


def test_quality_payload_carries_postgres_provenance(monkeypatch):
    """DA ran on the Postgres fallback — payload and rendered report must say so."""
    calls = {}

    def fake_run_sql(sql, *, mode="explore", max_rows=None, source="fabric"):
        calls["source"] = source
        return {"rows": [{"n": 1}], "columns": ["n"]}

    monkeypatch.setattr(
        quality_assembly,
        "enforce_row_count_threshold_for_source",
        lambda sql, source, settings=None: 1,
    )
    monkeypatch.setattr(quality_assembly, "run_sql", fake_run_sql)

    payload = build_quality_payload(_explore_state(sql_source="postgres"))
    assert payload["data_source"] == "postgres"
    assert calls["source"] == "postgres"

    rendered = format_explore_response_th(payload)
    assert "แหล่งข้อมูล" in rendered
    assert "สำรอง" in rendered


def test_quality_payload_carries_fabric_provenance(monkeypatch):
    monkeypatch.setattr(
        quality_assembly,
        "enforce_row_count_threshold_for_source",
        lambda sql, source, settings=None: 1,
    )
    monkeypatch.setattr(
        quality_assembly,
        "run_sql",
        lambda sql, *, mode="explore", max_rows=None, source="fabric": {
            "rows": [{"n": 1}],
            "columns": ["n"],
        },
    )
    payload = build_quality_payload(_explore_state(sql_source="fabric"))
    assert payload["data_source"] == "fabric"
    rendered = format_explore_response_th(payload)
    assert "Fabric" in rendered
    assert "แหล่งข้อมูล" in rendered


def test_quality_payload_offline_provenance(monkeypatch):
    monkeypatch.setattr(quality_assembly, "fabric_can_query", lambda: False)
    monkeypatch.setattr(quality_assembly, "pg_can_query", lambda: False)
    payload = build_quality_payload(_explore_state())
    assert payload["data_source"] == "offline"
    rendered = format_explore_response_th(payload)
    assert "Offline" in rendered


def test_backlog_persists_data_source(temp_storage):
    item = create_item({"question_th": "q", "data_source": "postgres"})
    assert item["data_source"] == "postgres"
    # Items created before Phase F have no data_source — schema must accept them.
    from backend.app.schemas.backlog import BacklogItemResponse

    legacy = {k: v for k, v in item.items() if k != "data_source"}
    assert BacklogItemResponse(**legacy).data_source == ""


@pytest.mark.anyio
async def test_summarize_adds_source_line_for_postgres():
    state = AgentState(
        mode="trusted",
        query_result="ANALYSIS: Trusted ยอดขาย 100 ล้านบาท",
        sql_source="postgres",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    out = await summarize_node(state)
    assert "แหล่งข้อมูล" in out["final_answer"]
    assert "สำรอง" in out["final_answer"]
    assert "ANALYSIS: Trusted ยอดขาย 100 ล้านบาท" in out["final_answer"]


@pytest.mark.anyio
async def test_summarize_no_source_line_when_sql_never_ran():
    state = AgentState(
        mode="trusted",
        query_result="ANALYSIS: draft (offline)",
        sql_source="",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    out = await summarize_node(state)
    assert "แหล่งข้อมูล" not in out["final_answer"]
