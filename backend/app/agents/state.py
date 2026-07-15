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

    # Routing
    next_agent: str = ""
    final_answer: str = ""

    model_config = {"arbitrary_types_allowed": True}
