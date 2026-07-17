import asyncio
import re

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
    enforce_row_count_threshold_for_source_async,
    fabric_can_query,
    pg_can_query,
    run_sql_async,
)
from backend.app.services.pdca_logger import log_sql_failure
from backend.app.services.pg_numeric_overlay import format_pg_numeric_context

# Single shared CEO-facing failure message (quality_assembly is the canonical
# home); the old local name is kept as an alias for existing imports/tests.
from backend.app.services.quality_assembly import (
    SQL_FAILED_CEO_MSG_TH as SQL_FAILED_SUMMARY_TH,
)
from backend.app.services.semantic_store import read_trusted_layer

MAX_SQL_ATTEMPTS = 3

# Failed-attempt marker lines carry friendly-error text from earlier attempts;
# once an attempt succeeds they must be stripped so trusted summarize never
# concatenates them into final_answer (Phase D residual, DA finding).
_SQL_ATTEMPT_FAILED_LINE_RE = re.compile(r"^SQL_ATTEMPT_FAILED:.*(?:\n|$)", re.MULTILINE)

# Postgres WH_Silver mirror — auto-fallback source. T-SQL and PostgreSQL are
# not interchangeable at the syntax level (TOP vs LIMIT, GETDATE() vs NOW(),
# bracket vs double-quote identifiers), so the active source must be decided
# *before* the LLM writes SQL, not translated after the fact.
_DIALECT_LABEL = {
    "fabric": "Microsoft Fabric Data Warehouse (T-SQL / Synapse dialect)",
    "postgres": "PostgreSQL (WH_Silver mirror — auto-fallback while Fabric is unreachable)",
}
# Most WH_Silver columns are physically varchar even when they hold numbers
# (verified live: Fabric INFORMATION_SCHEMA reports every VBRK column as
# varchar). T-SQL silently implicit-converts varchar in SUM()/AVG()/comparison;
# PostgreSQL refuses and errors immediately. CAST(col AS DECIMAL(18,2)) is
# valid in BOTH dialects, so SQL written with explicit casts survives a
# mid-retry source flip unchanged.
_CAST_GUIDANCE = (
    "- Numeric safety: most WH_Silver columns are stored as varchar even when they contain "
    "numbers. ALWAYS wrap columns in CAST(col AS DECIMAL(18,2)) before SUM/AVG/MIN/MAX, "
    "arithmetic, or numeric comparison — unless the schema context explicitly marks that "
    "column as a true numeric type. CAST(... AS DECIMAL(p,s)) works identically on both "
    "T-SQL and PostgreSQL; never rely on implicit varchar-to-number conversion "
    "(it happens to work on Fabric but fails hard on PostgreSQL)"
)
_DIALECT_RULES = {
    "fabric": (
        "- T-SQL syntax: use TOP N (not LIMIT) to cap rows, GETDATE() for current time, "
        "ISNULL() for null handling, [brackets] only if an identifier needs escaping\n"
        + _CAST_GUIDANCE
    ),
    "postgres": (
        "- PostgreSQL syntax: use LIMIT N (NOT TOP — TOP is invalid here), NOW() for current "
        "time, COALESCE() for null handling, double-quote identifiers only if case-sensitive\n"
        + _CAST_GUIDANCE
    ),
}


def _dialect_rules_for(source: str) -> str:
    """Dialect rules block for the prompt — plus, on the Postgres fallback,
    the D-2 numeric-column overlay (which mirror columns are truly numeric,
    so the LLM knows what needs CAST and what does not)."""
    rules = _DIALECT_RULES.get(source, _DIALECT_RULES["fabric"])
    if source == "postgres":
        overlay = format_pg_numeric_context()
        if overlay:
            rules = f"{rules}\n{overlay}"
    return rules


def _current_sql_source() -> str:
    """Resolve which connector should run SQL right now: 'fabric'|'postgres'|'offline'.

    Reads the module-level (monkeypatchable) `fabric_can_query`/`pg_can_query`
    rather than `fabric_sql.get_active_sql_source()` directly so tests that
    patch this module's `fabric_can_query` keep working unchanged.
    """
    if fabric_can_query():
        return "fabric"
    if pg_can_query():
        return "postgres"
    return "offline"


def strip_failed_attempt_lines(text: str) -> str:
    cleaned = _SQL_ATTEMPT_FAILED_LINE_RE.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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

SYSTEM_PROMPT = """You are a Data Analyst on an AI Data Team connected to {dialect_label}.

{skill}

Theme: {theme}
Mode: {mode}

Schema Context Pack (columns are authoritative):
{db_schema}

Knowledge layer:
{knowledge_context}

Metric Registry (approved executable KPIs — prefer these formulas):
{metric_registry_context}

WH_Silver SQL Reference (DDL column names — authoritative):
{sql_reference_context}

CEO feedback:
{ceo_feedback_context}

Team memory (onboarding baseline — align with this):
{team_memory_context}

Data Scientist guidance (hypotheses / approach — follow when writing SQL):
{analysis_summary}

Trusted definitions (if any):
{trusted_layer}

Rules:
- Generate ONLY SELECT queries — dialect: {dialect_label}
{dialect_rules}
- Respond in Thai for business explanation; keep SQL in English
- NEVER use unscoped SELECT * on large fact tables — require WHERE filters aligned to the question
- Always scope by time/org when the question implies it
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
    """Map an exception (or prior friendly summary) to a retry/PDCA class.

    Classes stay coarse on purpose: enough signal for guidance without
    embedding raw ODBC text into state.sql_error / quality_payload.
    """
    text = str(error)
    lower = text.lower()
    if isinstance(error, RowCountExceeded) or "เกินเกณฑ์" in text or "exceeds threshold" in lower:
        return "row_count"
    if (
        "Invalid column name" in text
        or "42S22" in text
        or "ชื่อคอลัมน์" in text
        or "42703" in text  # Postgres undefined_column SQLSTATE
        or ("column" in lower and "does not exist" in lower)  # psycopg2 UndefinedColumn text
    ):
        return "invalid_column"
    if (
        "timeout" in lower
        or "timed out" in lower
        or "HYT00" in text
        or "เกินเวลา" in text
        or "57014" in text  # Postgres query_canceled (statement_timeout)
    ):
        return "timeout"
    if (
        "connection" in lower
        or "login failed" in lower
        or "could not connect" in lower  # psycopg2 OperationalError
        or "08006" in text  # Postgres connection_failure SQLSTATE
        or "08001" in text
        or "08S01" in text
        or "เชื่อมต่อ" in text
    ):
        return "connection"
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
    if error_class == "timeout":
        return (
            "The previous SQL timed out. Narrow the query (filters, TOP/LIMIT, smaller date range).\n"
            f"Error detail: {error}"
        )
    if error_class == "connection":
        return (
            "The previous SQL failed due to a database connection problem. "
            "Keep the same SELECT shape; a reconnect may succeed on retry.\n"
            f"Error detail: {error}"
        )
    return (
        "The previous SQL failed. Fix the syntax/logic and keep it a single SELECT/WITH.\n"
        f"Error detail: {error}"
    )


def _friendly_sql_error(error: BaseException) -> str:
    """CEO/job-visible SQL error: exception type + class, never raw ODBC text."""
    if isinstance(error, RowCountExceeded):
        return error.message_th
    klass = _classify_sql_error(error)
    type_name = type(error).__name__
    if klass == "invalid_column":
        return f"ชื่อคอลัมน์ใน SQL ไม่ถูกต้อง ({type_name})"
    if klass == "timeout":
        return f"การรัน SQL เกินเวลาที่กำหนด ({type_name})"
    if klass == "connection":
        return f"เชื่อมต่อฐานข้อมูลไม่สำเร็จ ({type_name})"
    return f"รัน SQL ไม่สำเร็จ ({type_name})"


async def _retry_sql_with_error(
    content: str,
    sql: str,
    error: str,
    db_schema: str,
    *,
    error_class: str | None = None,
    mode: str = "explore",
) -> tuple[str, str, str]:
    """Ask the LLM to fix SQL for the given error class; execute if a fix is produced.

    Resolves the active source fresh (a Fabric failure just before this call
    may have flipped the reachability cache to Postgres) so the retry's SQL
    always targets the dialect it will actually run against. Returns
    (content, fixed_sql, source_used).
    """
    source = _current_sql_source()
    klass = error_class or _classify_sql_error(error)
    guidance = _retry_guidance(klass, error)
    dialect_rules = _dialect_rules_for(source)
    retry_prompt = f"""{guidance}

Target SQL dialect: {_DIALECT_LABEL.get(source, _DIALECT_LABEL["fabric"])}
{dialect_rules}

Original SQL:
{sql}

Available schema (use ONLY these columns):
{db_schema[:3000]}

Fix the SQL. Return corrected SQL only in a ```sql block."""
    response = await llm.ainvoke(retry_prompt)
    fixed = _extract_sql(str(response.content))
    if not fixed:
        raise RuntimeError("Retry LLM did not return SQL")
    await enforce_row_count_threshold_for_source_async(fixed, source)
    result = await run_sql_async(fixed, mode=mode, max_rows=10, source=source)
    return (
        strip_failed_attempt_lines(content)
        + f"\n\nSQL_RETRY:\n{fixed}\n\nQUERY_RESULT:\n{result.get('rows', [])}",
        fixed,
        result.get("source", source),
    )


async def _execute_sql_with_guard(sql: str, mode: str) -> dict:
    source = _current_sql_source()
    await enforce_row_count_threshold_for_source_async(sql, source)
    return await run_sql_async(sql, mode=mode, max_rows=10, source=source)


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
    # Decided once up front: which connector/dialect this invocation targets.
    source = _current_sql_source()
    dialect_label = _DIALECT_LABEL.get(source, _DIALECT_LABEL["fabric"])
    dialect_rules = _dialect_rules_for(source)

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
    if state.sql_error and sql and source != "offline":
        try:
            content = content or state.query_result or ""
            content, sql, used_source = await _retry_sql_with_error(
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
                "sql_source": used_source,
                "step_errors": step_errors,
            }
        except Exception as e:
            return await _fail_sql_attempt(
                state, content or state.query_result or "", sql, e, theme_id, user_prompt, step_errors, source
            )
    elif state.sql_error and sql and source == "offline":
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
                metric_registry_context=state.metric_registry_context or "(none)",
                sql_reference_context=state.sql_reference_context or "(none)",
                ceo_feedback_context=state.ceo_feedback_context or "(none)",
                team_memory_context=state.team_memory_context or "(none)",
                analysis_summary=state.analysis_summary or "(none)",
                trusted_layer=trusted_text,
                schema_info=state.schema_info,
                mode_rules=mode_rules,
                dialect_label=dialect_label,
                dialect_rules=dialect_rules,
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
    if sql and source != "offline":
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
                "sql_source": result.get("source", source),
                "step_errors": step_errors,
            }
        except Exception as e:
            logger.exception("SQL execution failed (source=%s)", source)
            return await _fail_sql_attempt(
                state, content, sql, e, theme_id, user_prompt, step_errors, source
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
    source: str = "fabric",
) -> dict:
    friendly = _friendly_sql_error(error)
    new_count = state.sql_retry_count + 1
    try:
        from backend.app.services.progress_reporter import note_substep

        note_substep(state.thread_id, f"SQL รอบที่ {new_count}/{MAX_SQL_ATTEMPTS}")
    except Exception:
        pass
    # PDCA is file-only — keep full exception text there for debugging.
    # Job/CEO surfaces use ``friendly`` (type + class, no raw ODBC).
    await log_sql_failure(
        theme_id,
        user_prompt,
        sql,
        f"{type(error).__name__}: {error}",
        new_count,
        source=source,
    )
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
        "sql_source": source,
        "sql_error": friendly,
        "sql_failed": sql_failed,
        "step_errors": step_errors,
    }
