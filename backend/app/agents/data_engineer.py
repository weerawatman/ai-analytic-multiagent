from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.semantic_store import read_semantic_layer

settings = get_settings()

llm = ChatOllama(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    temperature=0,
    timeout=300,
)

# ── SQLDatabase Tool (ใช้ sync connection string สำหรับ LangChain SQLDatabase) ──
db = SQLDatabase.from_uri(settings.database_url_sync)
sql_tool = QuerySQLDatabaseTool(db=db)

SYSTEM_PROMPT = """You are an expert Data Engineer with DIRECT ACCESS to a PostgreSQL database via tools.
ALWAYS use tools to query data and NEVER claim you lack permissions.
You CAN and MUST run SQL queries to inspect the database.

Your responsibilities:
1. Analyze database schema and table structures by running real SQL queries
2. Build and maintain a semantic layer that maps business terms to database columns
3. Provide schema information to other agents

Available database schema (from live introspection):
{db_schema}

Current semantic layer:
{semantic_layer}

IMPORTANT INSTRUCTIONS:
- To list tables, the tool has already retrieved them above in "Available database schema"
- You can run SQL like: SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'xxx'
- You can run: SELECT * FROM xxx LIMIT 5  to see sample data
- NEVER say "I don't have access" or "I cannot connect" — you ALWAYS have access
- When the user asks about the database, ALWAYS provide concrete answers with real data

Respond with:
- SCHEMA: relevant table/column information (from actual database)
- SEMANTIC_UPDATE: any proposed changes to the semantic layer (or "none")
- SUMMARY: brief explanation of what you found
"""


async def data_engineer_node(state: AgentState) -> dict:
    """Data Engineer agent: extracts schema info and manages semantic layer."""
    logger.info("Data Engineer agent invoked for thread=%s", state.thread_id)

    semantic_layer = await read_semantic_layer()

    # ── ดึง schema จริงจาก DB ──
    try:
        db_schema = db.get_table_info()
        logger.info("DB schema introspection OK — tables found: %s", db.get_usable_table_names())
    except Exception as e:
        logger.error("Failed to introspect DB schema: %s", e)
        db_schema = f"(schema introspection failed: {e})"

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                db_schema=db_schema,
                semantic_layer=semantic_layer,
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
        logger.error("Data Engineer LLM call failed: %s", e)
        content = f"Data Engineer error: {e}"

    # ── ลอง run SQL ที่ LLM สร้าง (ถ้ามี) ──
    sql_to_run = _extract_sql(content)
    if sql_to_run:
        logger.info("Data Engineer executing SQL:\n%s", sql_to_run)
        try:
            sql_result = sql_tool.run(sql_to_run)
            logger.info("SQL result:\n%s", sql_result[:500])
            content += f"\n\nSQL_RESULT:\n{sql_result}"
        except Exception as e:
            logger.error("SQL execution failed: %s", e)
            content += f"\n\nSQL_ERROR: {e}"

    has_semantic_update = (
        "SEMANTIC_UPDATE:" in content
        and "none" not in content.lower().split("SEMANTIC_UPDATE:")[-1][:50]
    )

    logger.info("Data Engineer completed. Has semantic update: %s", has_semantic_update)

    return {
        "messages": [AIMessage(content=content, name="data_engineer")],
        "current_agent": "data_engineer",
        "schema_info": content,
        "semantic_layer": semantic_layer,
        "requires_approval": has_semantic_update,
        "approval_status": "pending" if has_semantic_update else "",
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
        lines = []
        for line in sql_part.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith(("ANALYSIS:", "SEMANTIC_UPDATE:", "SUMMARY:", "SCHEMA:")):
                lines.append(stripped)
            elif stripped.startswith(("ANALYSIS:", "SEMANTIC_UPDATE:", "SUMMARY:", "SCHEMA:")):
                break
        return " ".join(lines)

    return ""
