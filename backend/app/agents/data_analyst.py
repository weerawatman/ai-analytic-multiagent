from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger

settings = get_settings()

llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    temperature=0,
    timeout=300,
)

# ── SQLDatabase Tool (ดึงค่าจาก .env ผ่าน config.py) ──
db = SQLDatabase.from_uri(settings.database_url_sync)
sql_tool = QuerySQLDatabaseTool(db=db)

SYSTEM_PROMPT = """You are a Data Analyst agent with DIRECT ACCESS to a PostgreSQL database.
You CAN and MUST run SQL queries. NEVER claim you lack access.

Your responsibilities:
1. Convert natural language questions into SQL queries (Text-to-SQL)
2. Run queries against the real database and analyze results
3. Provide clear, business-friendly explanations

Available database schema:
{db_schema}

Additional context from Data Engineer:
{schema_info}

IMPORTANT:
- Generate ONLY SELECT queries (never INSERT, UPDATE, DELETE, DROP, etc.)
- Use the PostgreSQL dialect
- ALWAYS provide a concrete SQL query — do NOT just describe what you would do
- Format your response as:
  SQL: <your query>
  ANALYSIS: <explanation of what the query does and expected insights>
"""


async def data_analyst_node(state: AgentState) -> dict:
    """Data Analyst agent: generates SQL, runs it, and analyzes data patterns."""
    logger.info("Data Analyst agent invoked for thread=%s", state.thread_id)

    # ── ดึง schema จริงจาก DB ──
    try:
        db_schema = db.get_table_info()
        logger.info("Data Analyst DB introspection OK — tables: %s", db.get_usable_table_names())
    except Exception as e:
        logger.error("Data Analyst failed to introspect DB: %s", e)
        db_schema = f"(schema introspection failed: {e})"

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                db_schema=db_schema,
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

    # ── Extract & Execute SQL ──
    sql = _extract_sql(content)
    sql_result = ""

    if sql:
        logger.info("=" * 60)
        logger.info("DATA ANALYST — Generated SQL Query:")
        logger.info(sql)
        logger.info("=" * 60)

        # Safety check: only SELECT
        if sql.strip().upper().startswith("SELECT"):
            try:
                sql_result = sql_tool.run(sql)
                logger.info("SQL execution result (first 500 chars):\n%s", sql_result[:500])
                content += f"\n\nQUERY_RESULT:\n{sql_result}"
            except Exception as e:
                logger.error("SQL execution failed: %s", e)
                content += f"\n\nSQL_ERROR: {e}"
                sql_result = f"Error: {e}"
        else:
            logger.warning("BLOCKED non-SELECT query: %s", sql[:100])
            content += "\n\nSQL_ERROR: Only SELECT queries are allowed."
    else:
        logger.warning("Data Analyst did not produce a SQL query")

    logger.info("Data Analyst completed. Generated SQL length: %d", len(sql))

    return {
        "messages": [AIMessage(content=content, name="data_analyst")],
        "current_agent": "data_analyst",
        "generated_sql": sql,
        "query_result": content,
    }


def _extract_sql(text: str) -> str:
    """Extract SQL from markdown code blocks or inline SQL: tags."""
    import re

    # Try ```sql ... ``` first
    match = re.search(r"```sql\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try SQL: tag
    if "SQL:" in text:
        sql_part = text.split("SQL:")[-1]
        end_marker = "ANALYSIS:"
        if end_marker in sql_part:
            sql_part = sql_part.split(end_marker)[0]
        return sql_part.strip()

    return ""
