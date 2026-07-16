import operator
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(BaseModel):
    """Shared state across all agents in the LangGraph workflow."""

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    current_agent: str = "orchestrator"
    thread_id: str = ""

    # Data Engineer outputs
    schema_info: str = ""
    semantic_layer: dict = Field(default_factory=dict)
    requires_approval: bool = False
    approval_status: Literal["pending", "approved", "rejected", ""] = ""

    # Data Analyst outputs
    generated_sql: str = ""
    query_result: str = ""

    # Data Scientist outputs
    analysis_summary: str = ""

    # Business Analyst outputs (Phase 2)
    ba_summary: str = ""

    # Phase 2 context
    theme_id: str = ""
    discovery_context: str = ""
    knowledge_context: str = ""
    sql_reference_context: str = ""
    ceo_feedback_context: str = ""
    team_memory_context: str = ""
    role_briefs: list[dict] = Field(default_factory=list)
    use_collaborative_flow: bool = True

    # Routing
    next_agent: str = ""
    final_answer: str = ""

    # Explore / Trusted context
    mode: Literal["explore", "trusted"] = "explore"
    theme: str = ""

    # Quality Bar D payload
    quality_payload: dict = Field(default_factory=dict)

    # Structured per-node errors (accumulated across nodes; nodes also keep
    # embedding errors in content so pipeline behavior is unchanged)
    step_errors: Annotated[list[str], operator.add] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
