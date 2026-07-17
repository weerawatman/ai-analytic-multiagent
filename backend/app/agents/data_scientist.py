from langchain_core.messages import AIMessage

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger

llm = make_chat_ollama(temperature=0.2)

SQL_FAILED_CRITIQUE_TH = (
    "CRITIQUE: ยังไม่สามารถ critique เชิงวิเคราะห์ได้ เนื่องจาก SQL รันไม่สำเร็จหลังลองปรับครบ 3 ครั้ง "
    "— แนะนำให้ปรับคำถามให้เจาะจงขึ้น (ระบุช่วงเวลา/หน่วยงาน) แล้วถามใหม่"
)

CRITIQUE_PROMPT = """{skill}

You are a Data Scientist reviewing a draft analytics insight (Explore mode).
Challenge assumptions and suggest improvements. Respond in Thai for narrative; SQL in English.

Discovery context:
{discovery_context}

Knowledge:
{knowledge_context}

CEO feedback:
{ceo_feedback_context}

Team memory:
{team_memory_context}

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

SYSTEM_PROMPT = """{skill}

You are a Data Scientist agent for exploratory analytics (not ML deployment).

Context:
- Schema: {schema_info}
- Discovery: {discovery_context}
- Analyst output: {query_result}

Respond in Thai. Suggest analytical angles, challenge assumptions, propose checks.
Include ALT_SQL, ASSUMPTIONS, UNKNOWNS, QUESTIONS_FOR_BA_DA, CONFIDENCE, CRITIQUE sections.
"""


async def explore_critique_node(state: AgentState) -> dict:
    """Challenge analyst assumptions in Explore pipeline."""
    logger.info("Explore critique node thread=%s", state.thread_id)

    # Phase D graceful degradation — with sql_failed the analyst output is
    # failure text; critiquing it would only echo error detail into the CEO
    # report. Return a deterministic polite note instead of calling the LLM.
    if state.sql_failed:
        return {
            "messages": [AIMessage(content=SQL_FAILED_CRITIQUE_TH, name="data_scientist")],
            "current_agent": "data_scientist",
            "analysis_summary": SQL_FAILED_CRITIQUE_TH,
            "step_errors": [],
        }

    skill = load_agent_skill("data_scientist")

    messages = [
        {
            "role": "system",
            "content": CRITIQUE_PROMPT.format(
                skill=skill,
                discovery_context=state.discovery_context or "(none)",
                knowledge_context=state.knowledge_context or "(none)",
                ceo_feedback_context=state.ceo_feedback_context or "(none)",
                team_memory_context=state.team_memory_context or "(none)",
                query_result=state.query_result,
            ),
        }
    ]

    step_errors: list[str] = []
    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.exception("Critique LLM failed")
        content = f"CRITIQUE: ไม่สามารถ critique ได้ชั่วคราว ({type(e).__name__})"
        step_errors.append(f"explore_critique: {e}")

    return {
        "messages": [AIMessage(content=content, name="data_scientist")],
        "current_agent": "data_scientist",
        "analysis_summary": content,
        "step_errors": step_errors,
    }


async def data_scientist_node(state: AgentState) -> dict:
    logger.info("Data Scientist agent invoked thread=%s", state.thread_id)
    skill = load_agent_skill("data_scientist")

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                skill=skill,
                schema_info=state.schema_info,
                discovery_context=state.discovery_context or "(none)",
                query_result=state.query_result,
            ),
        },
    ] + [
        {"role": m.type if m.type in ("human", "system") else "assistant", "content": m.content}
        for m in state.messages[-5:]
    ]

    step_errors: list[str] = []
    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.exception("Data Scientist LLM call failed")
        content = f"Data Scientist ไม่พร้อมชั่วคราว ({type(e).__name__}) — ลองใหม่อีกครั้ง"
        step_errors.append(f"data_scientist: {e}")

    return {
        "messages": [AIMessage(content=content, name="data_scientist")],
        "current_agent": "data_scientist",
        "analysis_summary": content,
        "final_answer": content,
        "step_errors": step_errors,
    }
