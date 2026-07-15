from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger

settings = get_settings()

llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    temperature=0.2,
    timeout=300,
)

SYSTEM_PROMPT = """You are a Data Scientist agent. Your responsibilities:
1. Propose statistical models and machine learning approaches based on available data
2. Interpret analysis results from the Data Analyst
3. Suggest advanced analytics, forecasting, or segmentation strategies

Context from previous agents:
- Schema info: {schema_info}
- Query results: {query_result}

Respond with:
- MODEL_SUGGESTION: recommended approach (regression, classification, clustering, etc.)
- RATIONALE: why this approach fits the data and business question
- NEXT_STEPS: actionable recommendations
"""


async def data_scientist_node(state: AgentState) -> dict:
    """Data Scientist agent: proposes models and advanced analytics."""
    logger.info("Data Scientist agent invoked for thread=%s", state.thread_id)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                schema_info=state.schema_info,
                query_result=state.query_result,
            ),
        },
    ] + [
        {"role": m.type if m.type in ("human", "system") else "assistant", "content": m.content}
        for m in state.messages[-5:]
    ]

    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.error("Data Scientist LLM call failed: %s", e)
        content = f"Data Scientist error: {e}"

    logger.info("Data Scientist completed")

    return {
        "messages": [AIMessage(content=content, name="data_scientist")],
        "current_agent": "data_scientist",
        "analysis_summary": content,
        "final_answer": content,
    }
