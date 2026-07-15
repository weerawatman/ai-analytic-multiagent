from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.app.agents.data_analyst import data_analyst_node
from backend.app.agents.data_engineer import data_engineer_node
from backend.app.agents.data_scientist import data_scientist_node
from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger

settings = get_settings()

router_llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    temperature=0,
    timeout=300,
)

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
    """Router: decides which agent handles the request."""
    last_message = ""
    for m in reversed(state.messages):
        if isinstance(m, HumanMessage):
            last_message = m.content
            break

    logger.info("Routing message: %s...", last_message[:80])

    try:
        response = await router_llm.ainvoke(
            ROUTER_PROMPT.format(message=last_message)
        )
        raw: str = response.content.strip().lower()  # type: ignore[assignment]
    except Exception as e:
        logger.error("Router LLM call failed: %s", e)
        raw = "data_analyst"

    valid_agents = {"data_engineer", "data_analyst", "data_scientist"}
    next_agent = raw if raw in valid_agents else "data_analyst"

    logger.info("Routed to: %s", next_agent)
    return {"next_agent": next_agent}


def route_decision(state: AgentState) -> str:
    """Conditional edge: pick the next agent based on router output."""
    return state.next_agent


def approval_check(state: AgentState) -> str:
    """After Data Engineer, check if human approval is needed."""
    if state.requires_approval:
        logger.info("Approval required — interrupting graph")
        return "wait_for_approval"
    return "continue"


async def approval_gate_node(state: AgentState) -> dict:
    """Human-in-the-loop gate. The graph interrupts here.
    When resumed, approval_status will be set by the API."""
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
    else:
        return {
            "messages": [AIMessage(content="Semantic layer update rejected by user.", name="system")],
            "requires_approval": False,
            "final_answer": "Update rejected. No changes were made to the semantic layer.",
        }


def after_approval(state: AgentState) -> str:
    """Route after approval gate."""
    if state.approval_status == "approved":
        return "continue"
    return "end"


async def summarize_node(state: AgentState) -> dict:
    """Final node: produce a summary from all agent outputs."""
    parts: list[str] = []
    if state.schema_info:
        parts.append(f"[Data Engineer]\n{state.schema_info}")
    if state.query_result:
        parts.append(f"[Data Analyst]\n{state.query_result}")
    if state.analysis_summary:
        parts.append(f"[Data Scientist]\n{state.analysis_summary}")

    summary = "\n\n---\n\n".join(parts) if parts else "No output produced."
    return {"final_answer": summary}


# ──────────────────── Build the Graph ────────────────────

def build_graph() -> StateGraph:
    """Construct the LangGraph workflow with Human-in-the-Loop."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("router", route_node)
    builder.add_node("data_engineer", data_engineer_node)
    builder.add_node("data_analyst", data_analyst_node)
    builder.add_node("data_scientist", data_scientist_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("summarize", summarize_node)

    # Entry
    builder.set_entry_point("router")

    # Router → agent
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "data_engineer": "data_engineer",
            "data_analyst": "data_analyst",
            "data_scientist": "data_scientist",
        },
    )

    # Data Engineer → approval check
    builder.add_conditional_edges(
        "data_engineer",
        approval_check,
        {
            "wait_for_approval": "approval_gate",
            "continue": "summarize",
        },
    )

    # Approval gate → continue or end
    builder.add_conditional_edges(
        "approval_gate",
        after_approval,
        {
            "continue": "summarize",
            "end": END,
        },
    )

    # Other agents → summarize
    builder.add_edge("data_analyst", "summarize")
    builder.add_edge("data_scientist", "summarize")

    # Summarize → end
    builder.add_edge("summarize", END)

    return builder


# ──────────────────── Compile with Checkpointer ────────────────────

checkpointer = MemorySaver()

graph = build_graph().compile(
    checkpointer=checkpointer,
    interrupt_before=["approval_gate"],  # Human-in-the-loop interrupt
)
