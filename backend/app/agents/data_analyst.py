from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.discovery_service import format_schema_context_pack
from backend.app.services.fabric_sql import fabric_is_available, run_fabric_sql
from backend.app.services.semantic_store import read_trusted_layer


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
"""

settings = get_settings()

llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model_analyst or settings.ollama_model,
    temperature=0,
    timeout=settings.ollama_timeout,
)

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


async def _retry_sql_with_error(content: str, sql: str, error: str, db_schema: str) -> tuple[str, str]:
    """One retry round with column context when SQL fails."""
    retry_prompt = f"""The SQL failed with error: {error}

Original SQL:
{sql}

Available schema (use ONLY these columns):
{db_schema[:3000]}

Fix the SQL. Return corrected SQL only in a ```sql block."""
    try:
        response = await llm.ainvoke(retry_prompt)
        fixed = _extract_sql(str(response.content))
        if fixed:
            result = run_fabric_sql(fixed, mode="explore", max_rows=10)
            return content + f"\n\nSQL_RETRY:\n{fixed}\n\nQUERY_RESULT:\n{result.get('rows', [])}", fixed
    except Exception as exc:
        logger.warning("SQL retry failed: %s", exc)
    return content, sql


async def data_analyst_node(state: AgentState) -> dict:
    logger.info("Data Analyst agent invoked thread=%s mode=%s", state.thread_id, state.mode)

    theme_id = state.theme_id or ""
    db_schema = (
        state.discovery_context
        or format_schema_context_pack(theme_id or None)
        if fabric_is_available()
        else "(Fabric not configured)"
    )
    trusted = await read_trusted_layer()
    relevant_metrics = _filter_trusted_metrics(trusted, state.theme or None)
    trusted_text = str(relevant_metrics)[:2000]
    mode_rules = TRUSTED_MODE_RULES if state.mode == "trusted" else EXPLORE_MODE_RULES
    skill = load_agent_skill("data_analyst")

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

    try:
        response = await llm.ainvoke(messages)
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        logger.error("Data Analyst LLM call failed: %s", e)
        content = f"Data Analyst error: {e}"

    sql = _extract_sql(content)
    if sql and fabric_is_available():
        try:
            result = run_fabric_sql(sql, mode=state.mode, max_rows=10)
            content += f"\n\nQUERY_RESULT:\n{result.get('rows', [])}"
        except Exception as e:
            logger.error("Fabric SQL execution failed: %s", e)
            content += f"\n\nSQL_ERROR: {e}"
            if "Invalid column name" in str(e) or "42S22" in str(e):
                content, sql = await _retry_sql_with_error(content, sql, str(e), db_schema)

    return {
        "messages": [AIMessage(content=content, name="data_analyst")],
        "current_agent": "data_analyst",
        "generated_sql": sql,
        "query_result": content,
    }
