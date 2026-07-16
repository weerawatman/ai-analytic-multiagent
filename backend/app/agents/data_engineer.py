from langchain_core.messages import AIMessage

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.fabric_sql import (
    OFFLINE_SQL_MSG_TH,
    fabric_can_query,
    get_fabric_schema_text_async,
    run_fabric_sql_async,
)
from backend.app.services.semantic_store import read_semantic_layer

llm = make_chat_ollama(temperature=0)

SYSTEM_PROMPT = """{skill}

You are an expert Data Engineer with access to Microsoft Fabric Data Warehouse (T-SQL).

Theme: {theme}

Schema preview:
{db_schema}

Discovery context:
{discovery_context}

Knowledge:
{knowledge_context}

WH_Silver SQL Reference:
{sql_reference_context}

Team memory (onboarding baseline):
{team_memory_context}

CEO Feedback (นำไปปรับการทำงาน):
{ceo_feedback_context}

Current semantic layer:
{semantic_layer}

Rules:
- Use Fabric/T-SQL dialect for any SQL
- Respond in Thai for summaries; SQL in English
- Format:
  SCHEMA: <findings>
  SEMANTIC_UPDATE: none|<proposed change>
  SUMMARY: <Thai brief>
  SQL: <optional SELECT for inspection>
"""


async def data_engineer_node(state: AgentState) -> dict:
    logger.info("Data Engineer agent invoked thread=%s", state.thread_id)

    semantic_layer = await read_semantic_layer()
    discovery_ctx = state.discovery_context or "(none)"
    # Prefer discovery / state schema; only hit live Fabric when reachable
    if state.discovery_context and state.discovery_context.strip() not in ("", "(none)"):
        db_schema = state.discovery_context
    elif state.schema_info:
        db_schema = state.schema_info
    else:
        try:
            db_schema = await get_fabric_schema_text_async()
        except Exception as e:
            logger.warning("DE live schema fetch failed: %s", e)
            db_schema = f"(Fabric schema ไม่พร้อม: {e} — ใช้ discovery บนดิสก์ถ้ามี)"
    skill = load_agent_skill("data_engineer")
    knowledge_ctx = state.knowledge_context or "(none)"
    sql_ref_ctx = state.sql_reference_context or "(none)"
    team_ctx = state.team_memory_context or "(none)"

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                skill=skill,
                theme=state.theme or "ไม่ระบุ",
                db_schema=db_schema,
                discovery_context=discovery_ctx,
                knowledge_context=knowledge_ctx,
                sql_reference_context=sql_ref_ctx,
                team_memory_context=team_ctx,
                ceo_feedback_context=state.ceo_feedback_context or "(none)",
                semantic_layer=semantic_layer,
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
        logger.exception("Data Engineer LLM call failed")
        content = f"Data Engineer error: {e}"
        step_errors.append(f"data_engineer: {e}")

    if fabric_can_query() and "SQL:" in content:
        import re

        match = re.search(r"```sql\s*\n(.*?)```", content, re.DOTALL | re.IGNORECASE)
        sql = match.group(1).strip() if match else ""
        if sql:
            try:
                result = await run_fabric_sql_async(sql, mode=state.mode, max_rows=5)
                content += f"\n\nSQL_RESULT:\n{result.get('rows', [])}"
            except Exception as e:
                logger.exception("Data Engineer inspection SQL failed")
                content += f"\n\nSQL_ERROR: {e}"
                step_errors.append(f"data_engineer SQL: {e}")
    elif "SQL:" in content:
        content += f"\n\nSQL_SKIPPED: {OFFLINE_SQL_MSG_TH}"

    has_semantic_update = (
        "SEMANTIC_UPDATE:" in content
        and "none" not in content.lower().split("SEMANTIC_UPDATE:")[-1][:50]
    )

    return {
        "messages": [AIMessage(content=content, name="data_engineer")],
        "current_agent": "data_engineer",
        "schema_info": content,
        "semantic_layer": semantic_layer,
        "requires_approval": has_semantic_update,
        "approval_status": "pending" if has_semantic_update else "",
        "step_errors": step_errors,
    }
