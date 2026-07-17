from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.app.agents.business_analyst import business_analyst_node
from backend.app.agents.context_nodes import de_context_node, prepare_context_node
from backend.app.agents.data_analyst import (
    MAX_SQL_ATTEMPTS,
    data_analyst_node,
    strip_failed_attempt_lines,
)
from backend.app.agents.data_engineer import data_engineer_node
from backend.app.agents.data_scientist import data_scientist_node, explore_critique_node
from backend.app.agents.quality_node import quality_assembly_node
from backend.app.agents.state import AgentState
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.quality_assembly import (
    SQL_FAILED_CEO_MSG_TH,
    data_source_label_th,
)

router_llm = make_chat_ollama(temperature=0)

ROUTER_PROMPT = """You are a routing agent for an AI Data Team. Based on the user's message,
decide which specialist agent should handle it.

Agents available:
- data_engineer: Schema exploration, semantic layer, data modeling questions
- data_analyst: SQL queries, data analysis, reporting, dashboards
- data_scientist: Statistical modeling, ML, forecasting, advanced analytics

Respond with ONLY the agent name (data_engineer, data_analyst, or data_scientist).
If unsure, respond with data_analyst.

User message: {message}"""


async def route_node(state: AgentState) -> dict:
    last_message = ""
    for m in reversed(state.messages):
        if isinstance(m, HumanMessage):
            last_message = m.content
            break

    logger.info("Routing message: %s...", last_message[:80])

    try:
        response = await router_llm.ainvoke(ROUTER_PROMPT.format(message=last_message))
        raw: str = response.content.strip().lower()  # type: ignore[assignment]
    except Exception as e:
        logger.exception("Router LLM call failed")
        raw = "data_analyst"

    valid_agents = {"data_engineer", "data_analyst", "data_scientist"}
    next_agent = raw if raw in valid_agents else "data_analyst"
    logger.info("Routed to: %s", next_agent)
    return {"next_agent": next_agent}


def entry_decision(state: AgentState) -> str:
    if state.mode == "explore" and state.use_collaborative_flow:
        return "collaborative"
    return "router"


def route_decision(state: AgentState) -> str:
    return state.next_agent


def approval_check(state: AgentState) -> str:
    if state.requires_approval:
        logger.info("Approval required — interrupting graph")
        return "wait_for_approval"
    return "continue"


def after_analyst(state: AgentState) -> str:
    # Phase D — loop back to data_analyst while SQL errors remain and attempts remain.
    if (
        state.sql_error
        and not state.sql_failed
        and state.sql_retry_count < MAX_SQL_ATTEMPTS
    ):
        logger.info(
            "SQL retry loop-back attempt=%s/%s thread=%s",
            state.sql_retry_count,
            MAX_SQL_ATTEMPTS,
            state.thread_id,
        )
        return "retry_sql"
    if state.mode == "explore" and state.use_collaborative_flow:
        return "explore_critique"
    return "summarize" if state.mode == "trusted" else "explore_critique"


def after_scientist(state: AgentState) -> str:
    return "quality_assembly" if state.mode == "explore" else "summarize"


def after_critique_collab(state: AgentState) -> str:
    return "business_analyst" if state.use_collaborative_flow else "quality_assembly"


async def approval_gate_node(state: AgentState) -> dict:
    logger.info(
        "Approval gate: status=%s for thread=%s",
        state.approval_status,
        state.thread_id,
    )

    if state.approval_status == "approved":
        return {
            "messages": [AIMessage(content="Semantic layer update approved by user.", name="system")],
            "requires_approval": False,
        }
    return {
        "messages": [AIMessage(content="Semantic layer update rejected by user.", name="system")],
        "requires_approval": False,
        "final_answer": "Update rejected. No changes were made to the semantic layer.",
    }


def after_approval(state: AgentState) -> str:
    if state.approval_status == "approved":
        return "continue"
    return "end"


async def summarize_node(state: AgentState) -> dict:
    if state.final_answer:
        return {}

    # Phase D graceful degradation — on the trusted/router path there is no
    # quality_assembly node to clean up, and query_result carries raw
    # SQL_ATTEMPT_FAILED / exception text. Never concatenate that into the
    # CEO-facing answer; return the same polite Thai message Explore uses.
    if state.sql_failed:
        return {"final_answer": SQL_FAILED_CEO_MSG_TH}

    parts: list[str] = []
    # Provenance (Phase F): on the trusted/router path there is no
    # quality_assembly banner, so the source label goes here — the CEO must
    # know when numbers came from the Postgres fallback mirror, never silently.
    if state.sql_source in ("fabric", "postgres"):
        parts.append(f"แหล่งข้อมูล: {data_source_label_th(state.sql_source)}")
    if state.schema_info:
        parts.append(f"[Data Engineer]\n{state.schema_info}")
    if state.query_result:
        # Success-after-retry (or offline mid-retry) may still carry earlier
        # SQL_ATTEMPT_FAILED marker lines — never compose them into the answer.
        parts.append(f"[Data Analyst]\n{strip_failed_attempt_lines(state.query_result)}")
    if state.analysis_summary:
        parts.append(f"[Data Scientist]\n{state.analysis_summary}")
    if state.ba_summary:
        parts.append(f"[Business Analyst]\n{state.ba_summary}")

    summary = "\n\n---\n\n".join(parts) if parts else "No output produced."
    return {"final_answer": summary}


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("prepare_context", prepare_context_node)
    builder.add_node("router", route_node)
    builder.add_node("de_context", de_context_node)
    builder.add_node("data_engineer", data_engineer_node)
    builder.add_node("data_analyst", data_analyst_node)
    builder.add_node("data_scientist", data_scientist_node)
    builder.add_node("explore_critique", explore_critique_node)
    builder.add_node("business_analyst", business_analyst_node)
    builder.add_node("quality_assembly", quality_assembly_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("summarize", summarize_node)

    builder.set_entry_point("prepare_context")

    builder.add_conditional_edges(
        "prepare_context",
        entry_decision,
        {"collaborative": "de_context", "router": "router"},
    )

    # Collaborative Explore pipeline
    builder.add_edge("de_context", "data_analyst")
    builder.add_conditional_edges(
        "data_analyst",
        after_analyst,
        {
            "retry_sql": "data_analyst",
            "explore_critique": "explore_critique",
            "summarize": "summarize",
        },
    )

    builder.add_conditional_edges(
        "explore_critique",
        after_critique_collab,
        {"business_analyst": "business_analyst", "quality_assembly": "quality_assembly"},
    )
    builder.add_edge("business_analyst", "quality_assembly")
    builder.add_edge("quality_assembly", "summarize")

    # Router path (Trusted / explicit DE requests)
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "data_engineer": "data_engineer",
            "data_analyst": "data_analyst",
            "data_scientist": "data_scientist",
        },
    )

    builder.add_conditional_edges(
        "data_engineer",
        approval_check,
        {"wait_for_approval": "approval_gate", "continue": "summarize"},
    )

    builder.add_conditional_edges(
        "approval_gate",
        after_approval,
        {"continue": "summarize", "end": END},
    )

    builder.add_conditional_edges(
        "data_scientist",
        after_scientist,
        {"quality_assembly": "quality_assembly", "summarize": "summarize"},
    )

    builder.add_edge("summarize", END)
    return builder


checkpointer = MemorySaver()

graph = build_graph().compile(
    checkpointer=checkpointer,
    interrupt_before=["approval_gate"],
)
