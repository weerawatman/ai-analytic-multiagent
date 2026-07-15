from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.fabric_sql import fabric_is_available, get_fabric_schema_text, run_fabric_sql
from backend.app.services.semantic_store import read_trusted_layer

settings = get_settings()

llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    temperature=0,
    timeout=settings.ollama_timeout,
)

SYSTEM_PROMPT = """You are a Data Analyst on an AI Data Team connected to Microsoft Fabric Data Warehouse (T-SQL).

Theme: {theme}
Mode: {mode}

Schema preview (Fabric):
{db_schema}

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
  ANALYSIS: <Thai summary of insight — mark as Draft if mode=explore>

User question context from Data Engineer (if any):
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


async def data_analyst_node(state: AgentState) -> dict:
    logger.info("Data Analyst agent invoked thread=%s mode=%s", state.thread_id, state.mode)

    db_schema = get_fabric_schema_text() if fabric_is_available() else "(Fabric not configured)"
    trusted = await read_trusted_layer()
    trusted_text = str(trusted.get("metrics", []))[:1500]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                theme=state.theme or "ไม่ระบุ",
                mode=state.mode,
                db_schema=db_schema,
                trusted_layer=trusted_text,
                schema_info=state.schema_info,
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

    return {
        "messages": [AIMessage(content=content, name="data_analyst")],
        "current_agent": "data_analyst",
        "generated_sql": sql,
        "query_result": content,
    }
