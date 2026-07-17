"""LangGraph for Phase 2.5 team onboarding — DE → DS → DA → BA before CEO questions."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from backend.app.agents.context_nodes import build_phase2_context
from backend.app.agents.onboarding_nodes import (
    onboarding_ba_node,
    onboarding_da_node,
    onboarding_de_node,
    onboarding_ds_node,
    onboarding_finalize_node,
)


class OnboardingState(BaseModel):
    """Typed state so node updates merge — plain dict StateGraph replaces the whole state."""

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    theme_id: str = ""
    theme: str = ""
    thread_id: str = ""
    discovery_context: str = ""
    knowledge_context: str = ""
    sql_reference_context: str = ""
    ceo_feedback_context: str = ""
    homework_context: str = ""
    schema_info: str = ""
    query_result: str = ""
    analysis_summary: str = ""
    ba_summary: str = ""
    role_artifacts: dict = Field(default_factory=dict)
    status: str = "pending"
    team_summary: str = ""
    current_agent: str = ""
    prior_handoffs: str = ""

    model_config = {"arbitrary_types_allowed": True}


def build_onboarding_graph() -> StateGraph:
    builder = StateGraph(OnboardingState)

    builder.add_node("de_onboard", onboarding_de_node)
    builder.add_node("ds_onboard", onboarding_ds_node)
    builder.add_node("da_onboard", onboarding_da_node)
    builder.add_node("ba_onboard", onboarding_ba_node)
    builder.add_node("finalize", onboarding_finalize_node)

    builder.set_entry_point("de_onboard")
    builder.add_edge("de_onboard", "ds_onboard")
    builder.add_edge("ds_onboard", "da_onboard")
    builder.add_edge("da_onboard", "ba_onboard")
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

    from backend.app.services.deep_profile_service import format_homework_context

    ctx_state = AgentState(theme_id=theme_id, theme=theme_name, thread_id=f"onboard-{theme_id}")
    ctx = build_phase2_context(ctx_state)
    homework_context = format_homework_context(theme_id)
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
        "homework_context": homework_context,
        "schema_info": "",
        "query_result": "",
        "analysis_summary": "",
        "ba_summary": "",
        "role_artifacts": {},
        "status": "running",
    }
