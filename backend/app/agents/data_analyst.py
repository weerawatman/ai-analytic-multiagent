import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.discovery_service import format_schema_context_pack
from backend.app.services.fabric_sql import (
    OFFLINE_SQL_MSG_TH,
    RowCountExceeded,
    enforce_row_count_threshold_async,
    fabric_can_query,
    run_fabric_sql_async,
)
from backend.app.services.pdca_logger import log_sql_failure
from backend.app.services.semantic_store import read_trusted_layer

MAX_SQL_ATTEMPTS = 3

SQL_FAILED_SUMMARY_TH = (
    "ทีม Data Analyst ลองปรับ SQL แล้ว 3 ครั้งแต่ยังไม่สำเร็จ "
    "กรุณาปรับคำถามให้เจาะจงขึ้น เช่น ระบุช่วงเวลา หรือหน่วยงานที่สนใจ"
)


def _filter_trusted_metrics(trusted: dict, theme: str | None) -> list[dict]:
    metrics = trusted.get("metrics") or []
    if not theme:
        return metrics
    themed = [m for m in metrics if m.get("theme") == theme]
    return themed if themed else metrics


TRUSTED_MODE_RULES = """
TRUSTED MODE RULES (strict):
- Use ONLY metrics from the Trusted definitions list above — do NOT invent new metrics or filters
- SQL MUST follow sql_template, grain, and standard_filters from the matched Trusted metric
- If no Trusted metric matches the question, say so in Thai and list available metrics — do NOT guess
- Mark ANALYSIS section as Trusted (not Draft)
- Reference metric_key in your response when using a definition
"""

EXPLORE_MODE_RULES = """
EXPLORE MODE RULES:
- Use ONLY column names from Schema Context Pack — NEVER guess column names
- Propose draft SQL and mark ANALYSIS as Draft
- List assumptions and questions for BA/DA validation
- NEVER write unscoped SELECT * against large tables — always add WHERE filters that match the CEO question
  (date range, org unit, document type, etc.). Use row_count hints from the Schema Context Pack as a signal.
"""

settings = get_settings()

llm = make_chat_ollama(model=settings.ollama_model_analyst or None, temperature=0)

SYSTEM_PROMPT = """You are a Data Analyst on an AI Data Team connected to Microsoft Fabric Data Warehouse (T-SQL).

{skill}

Theme: {theme}
Mode: {mode}

Schema Context Pack (columns are authoritative):
{db_schema}

Knowledge layer:
{knowledge_context}

WH_Silver SQL Reference (DDL column names — authoritative):
{sql_reference_context}

CEO feedback:
{ceo_feedback_context}

Team memory (onboarding baseline — align with this):
{team_memory_context}

Trusted definitions (if any):
{trusted_layer}

Rules:
- Generate ONLY SELECT queries (T-SQL for Fabric/Synapse)
- Respond in Thai for business explanation; keep SQL in English
- NEVER use unscoped SELECT * on large fact tables — require WHERE filters aligned to the question
- Prefer TOP N when ranking; always scope by time/org when the question implies it
- ALWAYS include these sections:
  SQL: <primary query>
  ALT_SQL: <sanity check or alternative query>
  ASSUMPTIONS:
  - grain: ...
  - filters: ...
  CONFIDENCE: high|medium|low
  UNKNOWNS:
  - ...
  QUESTIONS_FOR_BA_DA:
  - ...
  ANALYSIS: <Thai summary — label as Draft or Trusted per mode>

{mode_rules}

Data Engineer context:
{schema_info}
"""


def _extract_sql(text: str) -> str:
    import re

    match = re.search(r"```sql\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if "SQL:" in text:
        sql_part = text.split("SQL:")[-1]
        for marker in ("ALT_SQL:", "ANALYSIS:", "ASSUMPTIONS:"):
            if marker in sql_part:
                sql_part = sql_part.split(marker)[0]
        return sql_part.strip()
    return ""


def _last_user_prompt(state: AgentState) -> str:
    for m in reversed(state.messages):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            return str(m.content)
    return ""


def _classify_sql_error(error: BaseException | str) -> str:
    text = str(error)
    if isinstance(error, RowCountExceeded) or "เกินเกณฑ์" in text or "exceeds threshold" in text.lower():
        return "row_count"
    if "Invalid column name" in text or "42S22" in text or "ชื่อคอลัมน์" in text:
        return "invalid_column"
    return "generic"


def _retry_guidance(error_class: str, error: str) -> str:
    if error_class == "row_count":
        return (
            "The previous query was rejected because the estimated result set is too large. "
            "Add or tighten WHERE filters (date range, organization, document type). "
            "Do NOT use unscoped SELECT *.\n"
            f"Error detail: {error}"
        )
    if error_class == "invalid_column":
        return (
            "The previous SQL used an invalid column name. "
            "Fix using ONLY columns from the schema context below.\n"
            f"Error detail: {error}"
        )
    return (
        "The previous SQL failed. Fix the syntax/logic and keep it a single SELECT/WITH.\n"
        f"Error detail: {error}"
    )


def _friendly_sql_error(error: BaseException) -> str:
    if isinstance(error, RowCountExceeded):
        return error.message_th
    klass = _classify_sql_error(error)
    if klass == "invalid_column":
        return f"ชื่อคอลัมน์ใน SQL ไม่ถูกต้อง ({type(error).__name__})"
    # Keep a short, non-traceback summary for the CEO-facing path.
    detail = str(error).splitlines()[0][:200]
    return f"รัน SQL ไม่สำเร็จ ({type(error).__name__}: {detail})"


async def _retry_sql_with_error(
    content: str,
    sql: str,
    error: str,
    db_schema: str,
    *,
    error_class: str | None = None,
    mode: str = "explore",
) -> tuple[str, str]:
    """Ask the LLM to fix SQL for the given error class; execute if a fix is produced."""
    klass = error_class or _classify_sql_error(error)
    guidance = _retry_guidance(klass, error)
    retry_prompt = f"""{guidance}

Original SQL:
{sql}

Available schema (use ONLY these columns):
{db_schema[:3000]}

Fix the SQL. Return corrected SQL only in a ```sql block."""
    response = await llm.ainvoke(retry_prompt)
    fixed = _extract_sql(str(response.content))
    if not fixed:
        raise RuntimeError("Retry LLM did not return SQL")
    await enforce_row_count_threshold_async(fixed)
    result = await run_fabric_sql_async(fixed, mode=mode, max_rows=10)
    return (
        content + f"\n\nSQL_RETRY:\n{fixed}\n\nQUERY_RESULT:\n{result.get('rows', [])}",
        fixed,
    )


async def _execute_sql_with_guard(sql: str, mode: str) -> dict:
    await enforce_row_count_threshold_async(sql)
    return await run_fabric_sql_async(sql, mode=mode, max_rows=10)


async def data_analyst_node(state: AgentState) -> dict:
    logger.info(
        "Data Analyst agent invoked thread=%s mode=%s retry=%s",
        state.thread_id,
        state.mode,
        state.sql_retry_count,
    )

    theme_id = state.theme_id or ""
    db_schema = state.discovery_context or await asyncio.to_thread(
        format_schema_context_pack, theme_id or None
    )
    if not (db_schema or "").strip() or db_schema.startswith("(no "):
        db_schema = (
            state.discovery_context
            or db_schema
            or "(ไม่มี discovery — เลือก theme ที่มี cache หรือรอ Fabric)"
        )
    trusted = await read_trusted_layer()
    relevant_metrics = _filter_trusted_metrics(trusted, state.theme or None)
    trusted_text = str(relevant_metrics)[:2000]
    mode_rules = TRUSTED_MODE_RULES if state.mode == "trusted" else EXPLORE_MODE_RULES
    skill = load_agent_skill("data_analyst")
    user_prompt = _last_user_prompt(state)

    if state.mode == "trusted" and not relevant_metrics:
        no_trusted_msg = (
            "[Trusted Mode] ยังไม่มี Trusted definition สำหรับ theme นี้ — "
            "promote insight จาก backlog ก่อน หรือสลับเป็น Explore mode"
        )
        return {
            "messages": [AIMessage(content=no_trusted_msg, name="data_analyst")],
            "current_agent": "data_analyst",
            "query_result": no_trusted_msg,
            "final_answer": no_trusted_msg,
        }

    step_errors: list[str] = []
    sql = state.generated_sql or ""
    content = state.query_result if state.sql_error else ""

    # --- Produce SQL (fresh generation or error-class retry) ---
    if state.sql_error and sql and fabric_can_query():
        try:
            content = content or state.query_result or ""
            content, sql = await _retry_sql_with_error(
                content,
                sql,
                state.sql_error,
                db_schema,
                error_class=_classify_sql_error(state.sql_error),
                mode=state.mode,
            )
            return {
                "messages": [AIMessage(content=content, name="data_analyst")],
                "current_agent": "data_analyst",
                "generated_sql": sql,
                "query_result": content,
                "sql_error": "",
                "sql_failed": False,
                "step_errors": step_errors,
            }
        except Exception as e:
            return await _fail_sql_attempt(
                state, content or state.query_result or "", sql, e, theme_id, user_prompt, step_errors
            )
    elif state.sql_error and sql and not fabric_can_query():
        content = (state.query_result or "") + f"\n\nSQL_SKIPPED: {OFFLINE_SQL_MSG_TH}"
        content += f"\nDRAFT_SQL:\n{sql}"
        return {
            "messages": [AIMessage(content=content, name="data_analyst")],
            "current_agent": "data_analyst",
            "generated_sql": sql,
            "query_result": content,
            "sql_error": "",
            "step_errors": step_errors,
        }

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                skill=skill,
                theme=state.theme or "ไม่ระบุ",
                mode=state.mode,
                db_schema=db_schema,
                knowledge_context=state.knowledge_context or "(none)",
                sql_reference_context=state.sql_reference_context or "(none)",
                ceo_feedback_context=state.ceo_feedback_context or "(none)",
                team_memory_context=state.team_memory_context or "(none)",
                trusted_layer=trusted_text,
                schema_info=state.schema_info,
                mode_rules=mode_rules,
            ),
        },
    ] + [
        {"role": m.type if m.type in ("human", "system") else "assistant", "content": m.content}
        for m in state.messages[-5:]
    ]
    if state.sql_error:
        messages.append(
            {
                "role": "user",
                "content": _retry_guidance(_classify_sql_error(state.sql_error), state.sql_error)
                + (f"\n\nPrevious SQL:\n{sql}" if sql else ""),
            }
        )

    try:
        response = await llm.ainvoke(messages)
        content = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.exception("Data Analyst LLM call failed")
        content = f"Data Analyst ไม่พร้อมชั่วคราว ({type(e).__name__}) — ลองใหม่อีกครั้ง"
        step_errors.append(f"data_analyst: {e}")

    sql = _extract_sql(content) or sql
    if sql and fabric_can_query():
        try:
            result = await _execute_sql_with_guard(sql, state.mode)
            content += f"\n\nQUERY_RESULT:\n{result.get('rows', [])}"
            return {
                "messages": [AIMessage(content=content, name="data_analyst")],
                "current_agent": "data_analyst",
                "generated_sql": sql,
                "query_result": content,
                "sql_error": "",
                "sql_failed": False,
                "step_errors": step_errors,
            }
        except Exception as e:
            logger.exception("Fabric SQL execution failed")
            return await _fail_sql_attempt(
                state, content, sql, e, theme_id, user_prompt, step_errors
            )

    if sql:
        content += f"\n\nSQL_SKIPPED: {OFFLINE_SQL_MSG_TH}"
        content += f"\nDRAFT_SQL:\n{sql}"

    return {
        "messages": [AIMessage(content=content, name="data_analyst")],
        "current_agent": "data_analyst",
        "generated_sql": sql,
        "query_result": content,
        "step_errors": step_errors,
    }


async def _fail_sql_attempt(
    state: AgentState,
    content: str,
    sql: str,
    error: BaseException,
    theme_id: str,
    user_prompt: str,
    step_errors: list[str],
) -> dict:
    friendly = _friendly_sql_error(error)
    new_count = state.sql_retry_count + 1
    await log_sql_failure(theme_id, user_prompt, sql, friendly, new_count)
    sql_failed = new_count >= MAX_SQL_ATTEMPTS
    content = (content or "") + f"\n\nSQL_ATTEMPT_FAILED: {friendly}"
    if sql_failed:
        content += f"\n\n{SQL_FAILED_SUMMARY_TH}"
    step_errors.append(f"data_analyst SQL: {friendly}")
    return {
        "messages": [AIMessage(content=content, name="data_analyst")],
        "current_agent": "data_analyst",
        "generated_sql": sql,
        "query_result": content,
        "sql_retry_count": new_count,
        "sql_error": friendly,
        "sql_failed": sql_failed,
        "step_errors": step_errors,
    }
