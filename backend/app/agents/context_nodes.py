"""Shared context helpers for Phase 2 agents."""

import asyncio

from backend.app.agents.state import AgentState
from backend.app.services.discovery_service import format_schema_context_pack
from backend.app.services.feedback_store import format_feedback_context
from backend.app.services.knowledge_store import format_knowledge_context
from backend.app.services.sql_reference_store import (
    format_sql_reference_context,
    get_table_refs_for_theme,
)
from backend.app.services.team_memory_store import format_team_memory_context


def _table_refs_for_theme(theme_id: str, discovery_text: str) -> list[str]:
    refs = get_table_refs_for_theme(theme_id) if theme_id else []
    if refs:
        return refs
    import re

    return re.findall(r"^##\s+(\S+)", discovery_text, re.MULTILINE)


def build_phase2_context(state: AgentState) -> dict[str, str]:
    theme_id = state.theme_id or ""
    discovery = format_schema_context_pack(theme_id or None)
    knowledge = format_knowledge_context(theme=state.theme or theme_id or None)
    feedback = format_feedback_context(theme_id or None)
    table_refs = _table_refs_for_theme(theme_id, discovery)
    sql_ref = format_sql_reference_context(table_refs, theme_id=theme_id or None)
    team_memory = format_team_memory_context(theme_id or None)
    metric_registry_ctx = ""
    from backend.app.core.config import get_settings

    if get_settings().metric_registry_in_prompt:
        from backend.app.services.metric_registry import format_metric_registry_context

        metric_registry_ctx = format_metric_registry_context(
            theme=state.theme or theme_id or None
        )
    if theme_id:
        # Deterministic profiling evidence rides with team memory so every
        # agent prompt that already includes the onboarding baseline also
        # sees verified row counts / date ranges / DQ flags.
        from backend.app.services.deep_profile_service import format_homework_context

        homework = format_homework_context(theme_id)
        if homework:
            team_memory = f"{team_memory}\n\n{homework}" if team_memory else homework
    return {
        "discovery_context": discovery,
        "knowledge_context": knowledge,
        "metric_registry_context": metric_registry_ctx,
        "sql_reference_context": sql_ref,
        "ceo_feedback_context": feedback,
        "team_memory_context": team_memory,
    }


async def prepare_context_node(state: AgentState) -> dict:
    # build_phase2_context may hit Fabric (schema fallback) — keep it off the event loop.
    ctx = await asyncio.to_thread(build_phase2_context, state)
    return ctx


async def de_context_node(state: AgentState) -> dict:
    """Lightweight DE pass using discovery — sets schema_info for downstream agents."""
    from langchain_core.messages import AIMessage
    from backend.app.agents.skill_loader import load_agent_skill
    from backend.app.core.llm import make_chat_ollama

    skill = load_agent_skill("data_engineer")
    llm = make_chat_ollama(temperature=0)

    prompt = f"""{skill}

Theme: {state.theme}
User question context from messages.

Discovery:
{state.discovery_context or '(run discovery first)'}

Knowledge:
{state.knowledge_context or '(none)'}

WH_Silver SQL Reference (authoritative column names):
{state.sql_reference_context or '(none)'}

Team memory (onboarding baseline):
{state.team_memory_context or '(none)'}

CEO feedback:
{state.ceo_feedback_context or '(none)'}

Summarize STRUCTURE, QUALITY, RELATIONSHIPS for the analyst. Thai + English table names.
Keep under 800 words."""

    last_msg = ""
    for m in reversed(state.messages):
        if hasattr(m, "content") and m.type == "human":
            last_msg = m.content
            break

    step_errors: list[str] = []
    try:
        response = await llm.ainvoke(f"{prompt}\n\nUser question: {last_msg}")
        content: str = response.content  # type: ignore[assignment]
    except Exception as e:
        from backend.app.core.logger import logger

        logger.exception("DE context LLM call failed")
        content = f"[DE Context] Using discovery metadata only.\n{state.discovery_context[:2000]}"
        step_errors.append(f"de_context: {e}")

    return {
        "messages": [AIMessage(content=content, name="data_engineer")],
        "current_agent": "data_engineer",
        "schema_info": content,
        "requires_approval": False,
        "step_errors": step_errors,
    }
