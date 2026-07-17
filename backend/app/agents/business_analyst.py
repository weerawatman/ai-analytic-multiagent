from langchain_core.messages import AIMessage

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.error_sanitizer import sanitize_step_errors
from backend.app.services.quality_assembly import SQL_FAILED_CEO_MSG_TH

settings = get_settings()

llm = make_chat_ollama(model=settings.ollama_model_ba or None, temperature=0.2)

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

Team memory (onboarding baseline):
{team_memory_context}

Analyst output:
{query_result}

Scientist critique:
{analysis_summary}

SQL pipeline status:
{sql_status}

Rules:
- Define metrics in plain Thai — mark as Draft
- Align to KPI targets if present in knowledge
- Frame so-what for executive decision
- If SQL failed after retries: explain politely in Thai that the team could not complete the query,
  ask the CEO to narrow the question (time range / org unit). NEVER paste raw exception/traceback.
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
    sql_status = "ok"
    if state.sql_failed:
        sql_status = (
            f"FAILED after {state.sql_retry_count} attempts. "
            f"Last error (summary): {state.sql_error or '(none)'}. "
            f"Tell the CEO: {SQL_FAILED_CEO_MSG_TH}"
        )
    elif state.step_errors:
        # step_errors carry raw exception detail — sanitize before it enters
        # the prompt so the LLM cannot echo ODBC text into the CEO narrative.
        sql_status = "warnings: " + "; ".join(sanitize_step_errors(state.step_errors[:5]))

    # When SQL fully failed, skip LLM and return a deterministic polite message
    # so raw SQL_ERROR strings never reach the CEO narrative.
    if state.sql_failed:
        content = (
            "METRIC_DEFINITION:\n(ยังไม่สามารถนิยามได้ — SQL รันไม่สำเร็จ)\n\n"
            f"BUSINESS_SUMMARY:\n{SQL_FAILED_CEO_MSG_TH}\n\n"
            "CEO_QUESTIONS:\n"
            "- ต้องการดูช่วงเวลาใด (เช่น เดือนนี้ / ปีนี้)?\n"
            "- ต้องการเจาะหน่วยงานหรือประเภทเอกสารใด?\n\n"
            "KPI_ALIGNMENT:\n(ยังไม่มีผลลัพธ์)\n\n"
            "RECOMMENDATION:\nปรับคำถามให้แคบลงแล้วถามใหม่ — ทีมจะลองรัน SQL อีกครั้ง"
        )
        return {
            "messages": [AIMessage(content=content, name="business_analyst")],
            "current_agent": "business_analyst",
            "ba_summary": content,
            "step_errors": [],
        }

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
                team_memory_context=state.team_memory_context or "(none)",
                query_result=state.query_result[:3000] if state.query_result else "(none)",
                analysis_summary=state.analysis_summary[:2000] if state.analysis_summary else "(none)",
                sql_status=sql_status,
            ),
        },
    ] + [
        {"role": m.type if m.type in ("human", "system") else "assistant", "content": m.content}
        for m in state.messages[-3:]
    ]

    step_errors: list[str] = []
    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.exception("BA LLM call failed")
        content = f"Business Analyst ไม่พร้อมชั่วคราว ({type(e).__name__}) — ลองใหม่อีกครั้ง"
        step_errors.append(f"business_analyst: {e}")

    return {
        "messages": [AIMessage(content=content, name="business_analyst")],
        "current_agent": "business_analyst",
        "ba_summary": content,
        "step_errors": step_errors,
    }
