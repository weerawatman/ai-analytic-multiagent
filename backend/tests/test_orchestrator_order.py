"""Orchestrator collaborative flow order: DE → DS → DA → BA."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from backend.app.agents.orchestrator import (
    after_analyst,
    after_explore_critique,
    build_graph,
)
from backend.app.agents.state import AgentState
from backend.app.services.job_runner import _next_step


def test_collaborative_explore_edges_de_ds_da_ba():
    """Static graph: de_context → explore_critique → data_analyst."""
    compiled = build_graph().compile()
    g = compiled.get_graph()
    edges = {(e.source, e.target) for e in g.edges}
    assert ("de_context", "explore_critique") in edges
    assert ("explore_critique", "data_analyst") in edges
    # Old direct DE→DA edge must be gone
    assert ("de_context", "data_analyst") not in edges


def test_after_explore_critique_routes_plan_to_da():
    state = AgentState(query_result="", use_collaborative_flow=True)
    assert after_explore_critique(state) == "data_analyst"


def test_after_explore_critique_routes_post_sql_to_ba():
    state = AgentState(query_result="ANALYSIS: draft", use_collaborative_flow=True)
    assert after_explore_critique(state) == "business_analyst"


def test_after_analyst_collab_goes_to_ba():
    state = AgentState(
        mode="explore",
        use_collaborative_flow=True,
        sql_error="",
        sql_failed=False,
    )
    assert after_analyst(state) == "business_analyst"


def test_next_step_predicts_de_ds_da_ba():
    assert _next_step("prepare_context", {}, "explore") == "de_context"
    assert _next_step("de_context", {"schema_info": "x"}, "explore") == "explore_critique"
    assert _next_step("explore_critique", {"analysis_summary": "plan"}, "explore") == "data_analyst"
    assert (
        _next_step(
            "data_analyst",
            {"query_result": "ok", "sql_error": "", "sql_failed": False},
            "explore",
        )
        == "business_analyst"
    )
    assert _next_step("business_analyst", {"ba_summary": "x"}, "explore") == "quality_assembly"


@pytest.mark.anyio
async def test_collaborative_execution_order_runtime():
    """Tiny stub graph mirroring production edges — assert node visit order."""
    order: list[str] = []

    async def de(state: AgentState) -> dict:
        order.append("de_context")
        return {"schema_info": "DE structure"}

    async def ds(state: AgentState) -> dict:
        order.append("explore_critique")
        return {"analysis_summary": "DS plan HYPOTHESES: growth"}

    async def da(state: AgentState) -> dict:
        order.append("data_analyst")
        return {"query_result": "DA SQL ok", "sql_error": "", "sql_failed": False}

    async def ba(state: AgentState) -> dict:
        order.append("business_analyst")
        return {"ba_summary": "BA summary"}

    async def done(state: AgentState) -> dict:
        order.append("quality_assembly")
        return {"final_answer": "done"}

    builder = StateGraph(AgentState)
    builder.add_node("de_context", de)
    builder.add_node("explore_critique", ds)
    builder.add_node("data_analyst", da)
    builder.add_node("business_analyst", ba)
    builder.add_node("quality_assembly", done)
    builder.set_entry_point("de_context")
    builder.add_edge("de_context", "explore_critique")
    builder.add_conditional_edges(
        "explore_critique",
        after_explore_critique,
        {
            "data_analyst": "data_analyst",
            "business_analyst": "business_analyst",
            "quality_assembly": "quality_assembly",
        },
    )
    builder.add_conditional_edges(
        "data_analyst",
        after_analyst,
        {
            "retry_sql": "data_analyst",
            "business_analyst": "business_analyst",
            "explore_critique": "explore_critique",
            "summarize": "quality_assembly",
        },
    )
    builder.add_edge("business_analyst", "quality_assembly")
    builder.add_edge("quality_assembly", END)
    graph = builder.compile()

    await graph.ainvoke(
        AgentState(
            messages=[HumanMessage(content="ยอดขาย")],
            mode="explore",
            use_collaborative_flow=True,
        )
    )
    assert order == [
        "de_context",
        "explore_critique",
        "data_analyst",
        "business_analyst",
        "quality_assembly",
    ]
