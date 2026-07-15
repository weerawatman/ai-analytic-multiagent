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
    timeout=settings.ollama_timeout,
)

CRITIQUE_PROMPT = """You are a Data Scientist reviewing a draft analytics insight (Explore mode).
Challenge assumptions and suggest improvements. Respond in Thai for narrative; SQL in English.

Analyst output:
{query_result}

Required sections:
ALT_SQL: <alternative or sanity-check query>
ASSUMPTIONS:
- <validated or challenged assumptions>
UNKNOWNS:
- <gaps>
QUESTIONS_FOR_BA_DA:
- <specific validation questions>
CONFIDENCE: high|medium|low
CRITIQUE: <Thai critique and suggested analytical angles — no ML training, strategy only>
"""

SYSTEM_PROMPT = """You are a Data Scientist agent for exploratory analytics (not ML deployment).

Context:
- Schema: {schema_info}
- Analyst output: {query_result}

Respond in Thai. Suggest analytical angles, challenge assumptions, propose checks.
Include ALT_SQL, ASSUMPTIONS, UNKNOWNS, QUESTIONS_FOR_BA_DA, CONFIDENCE, CRITIQUE sections.
"""


async def explore_critique_node(state: AgentState) -> dict:
    """Challenge analyst assumptions in Explore pipeline."""
    logger.info("Explore critique node thread=%s", state.thread_id)

    messages = [
        {
            "role": "system",
            "content": CRITIQUE_PROMPT.format(query_result=state.query_result),
        }
    ]

    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.error("Critique LLM failed: %s", e)
        content = f"CRITIQUE: ไม่สามารถ critique ได้: {e}"

    return {
        "messages": [AIMessage(content=content, name="data_scientist")],
        "current_agent": "data_scientist",
        "analysis_summary": content,
    }


async def data_scientist_node(state: AgentState) -> dict:
    logger.info("Data Scientist agent invoked thread=%s", state.thread_id)

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

    return {
        "messages": [AIMessage(content=content, name="data_scientist")],
        "current_agent": "data_scientist",
        "analysis_summary": content,
        "final_answer": content,
    }
