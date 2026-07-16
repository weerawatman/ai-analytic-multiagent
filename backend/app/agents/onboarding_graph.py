"""LangGraph for Phase 2.5 team onboarding — DE → DA → DS → BA before CEO questions."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from backend.app.agents.context_nodes import build_phase2_context
from backend.app.agents.onboarding_nodes import (
    onboarding_ba_node,
    onboarding_da_node,
    onboarding_de_node,
    onboarding_ds_node,
    onboarding_finalize_node,
)


def build_onboarding_graph() -> StateGraph:
    builder = StateGraph(dict)

    builder.add_node("de_onboard", onboarding_de_node)
    builder.add_node("da_onboard", onboarding_da_node)
    builder.add_node("ds_onboard", onboarding_ds_node)
    builder.add_node("ba_onboard", onboarding_ba_node)
    builder.add_node("finalize", onboarding_finalize_node)

    builder.set_entry_point("de_onboard")
    builder.add_edge("de_onboard", "da_onboard")
    builder.add_edge("da_onboard", "ds_onboard")
    builder.add_edge("ds_onboard", "ba_onboard")
    builder.add_edge("ba_onboard", "finalize")
    builder.add_edge("finalize", END)

    return builder


onboarding_graph = build_onboarding_graph().compile()


def build_onboarding_input(
    theme_id: str,
    theme_name: str,
) -> dict[str, Any]:
    from backend.app.agents.state import AgentState
    from backend.app.services.team_memory_store import get_or_create_team_memory

    ctx_state = AgentState(theme_id=theme_id, theme=theme_name, thread_id=f"onboard-{theme_id}")
    ctx = build_phase2_context(ctx_state)
    memory = get_or_create_team_memory(theme_id, theme_name)
    memory["status"] = "running"
    from backend.app.services.team_memory_store import save_team_memory

    save_team_memory(memory)

    return {
        "theme_id": theme_id,
        "theme": theme_name,
        "thread_id": f"onboard-{theme_id}",
        "discovery_context": ctx["discovery_context"],
        "knowledge_context": ctx["knowledge_context"],
        "sql_reference_context": ctx["sql_reference_context"],
        "ceo_feedback_context": ctx["ceo_feedback_context"],
        "schema_info": "",
        "query_result": "",
        "analysis_summary": "",
        "ba_summary": "",
        "role_artifacts": {},
        "status": "running",
    }
