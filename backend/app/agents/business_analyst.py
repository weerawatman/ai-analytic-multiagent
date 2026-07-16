from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger

settings = get_settings()

llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model_ba or settings.ollama_model,
    temperature=0.2,
    timeout=settings.ollama_timeout,
)

SYSTEM_PROMPT = """You are a Business Analyst on an AI Data Team presenting to the CEO.

Theme: {theme}
Mode: {mode}

{skill}

Discovery context:
{discovery_context}

Knowledge layer:
{knowledge_context}

CEO feedback to apply:
{ceo_feedback_context}

Analyst output:
{query_result}

Scientist critique:
{analysis_summary}

Rules:
- Define metrics in plain Thai — mark as Draft
- Align to KPI targets if present in knowledge
- Frame so-what for executive decision
- Required sections:
METRIC_DEFINITION:
BUSINESS_SUMMARY:
CEO_QUESTIONS:
KPI_ALIGNMENT:
RECOMMENDATION:
"""


async def business_analyst_node(state: AgentState) -> dict:
    logger.info("Business Analyst agent invoked thread=%s", state.thread_id)

    skill = load_agent_skill("business_analyst")
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                theme=state.theme or "ไม่ระบุ",
                mode=state.mode,
                skill=skill,
                discovery_context=state.discovery_context or "(none)",
                knowledge_context=state.knowledge_context or "(none)",
                ceo_feedback_context=state.ceo_feedback_context or "(none)",
                query_result=state.query_result[:3000] if state.query_result else "(none)",
                analysis_summary=state.analysis_summary[:2000] if state.analysis_summary else "(none)",
            ),
        },
    ] + [
        {"role": m.type if m.type in ("human", "system") else "assistant", "content": m.content}
        for m in state.messages[-3:]
    ]

    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.error("BA LLM call failed: %s", e)
        content = f"Business Analyst error: {e}"

    return {
        "messages": [AIMessage(content=content, name="business_analyst")],
        "current_agent": "business_analyst",
        "ba_summary": content,
    }
