"""Tests for Phase 2.5 context wiring."""

from backend.app.agents.context_nodes import build_phase2_context
from backend.app.agents.state import AgentState
from backend.app.services import team_memory_store


def test_build_phase2_includes_team_memory(temp_storage):
    team_memory_store.finalize_team_memory(
        "sales",
        team_summary="baseline ยอดขาย",
        recommended_tables=["SAPHANADB.CE1SATG_All_Cleaned"],
        key_metrics=["ยอดขายรายเดือน"],
    )
    state = AgentState(theme_id="sales", theme="ยอดขาย")
    ctx = build_phase2_context(state)
    assert "team_memory_context" in ctx
    assert "baseline" in ctx["team_memory_context"] or "Team Memory" in ctx["team_memory_context"]
