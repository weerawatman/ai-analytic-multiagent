"""Onboarding nodes — each role does homework before CEO asks questions.

Order: DE (structure) → DS (hypotheses / approach) → DA (metric + SQL draft) → BA (definitions).
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.team_memory_store import update_role_artifact


def _llm() -> ChatOllama:
    return make_chat_ollama(temperature=0.1)


def _parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _state_get(state: Any, key: str, default: Any = "") -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def _invoke_role(
    role: str,
    system: str,
    user_task: str,
) -> str:
    try:
        response = await _llm().ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_task},
            ]
        )
        return str(response.content).strip()
    except Exception as exc:
        # This string is written into team memory — keep only the exception
        # type; the full detail stays in the log.
        logger.exception("Onboarding %s failed: %s", role, exc)
        return (
            f"[Onboarding {role} ไม่สำเร็จ] ระบบขัดข้องชั่วคราว ({type(exc).__name__}) "
            "— รัน onboarding ใหม่อีกครั้งเพื่อให้ได้ handoff ครบ"
        )


def _base_context(state: Any) -> str:
    parts = [
        f"Theme: {_state_get(state, 'theme', '')} (id={_state_get(state, 'theme_id', '')})",
        f"\nDiscovery:\n{_state_get(state, 'discovery_context', '(none)')[:3500]}",
        f"\nKnowledge:\n{_state_get(state, 'knowledge_context', '(none)')[:2000]}",
        f"\nSQL Reference:\n{_state_get(state, 'sql_reference_context', '(none)')[:2000]}",
    ]
    prior = _state_get(state, "prior_handoffs", "")
    if prior:
        parts.append(f"\nPrior team handoffs:\n{prior[:2500]}")
    feedback = _state_get(state, "ceo_feedback_context", "")
    if feedback:
        parts.append(f"\nCEO feedback:\n{feedback[:1500]}")
    return "\n".join(parts)


def _theme_id(state: Any) -> str:
    theme_id = _state_get(state, "theme_id", "")
    if not theme_id:
        raise KeyError("theme_id")
    return str(theme_id)


async def onboarding_de_node(state: Any) -> dict[str, Any]:
    theme_id = _theme_id(state)
    theme = _state_get(state, "theme", "")
    skill = load_agent_skill("data_engineer")
    ctx = _base_context(state)
    prompt = f"""{skill}

You are onboarding this theme BEFORE the CEO asks questions.
Analyze structure, grain, keys, relationships, and data quality flags.

Return TWO parts:
1) HANDOFF: Thai summary (max 400 words) for the Data Scientist
2) JSON artifact on its own line:
{{"relationships":[{{"from_table":"","to_table":"","join_keys":"","notes_th":""}}],"quality_flags":[""],"primary_tables":[""]}}

{ctx}"""
    content = await _invoke_role("data_engineer", prompt, "Complete DE onboarding for this theme.")
    artifact = _parse_json_block(content)
    handoff = content.split("{")[0].replace("HANDOFF:", "").strip()[:2000]
    if not handoff:
        handoff = content[:2000]

    update_role_artifact(
        theme_id,
        "data_engineer",
        handoff_summary=handoff,
        artifact=artifact,
        theme_name=theme,
    )
    role_artifacts = dict(_state_get(state, "role_artifacts", {}) or {})
    role_artifacts["data_engineer"] = artifact
    return {
        "schema_info": handoff,
        "role_artifacts": role_artifacts,
        "messages": [AIMessage(content=handoff, name="data_engineer")],
        "current_agent": "data_engineer",
    }


async def onboarding_ds_node(state: Any) -> dict[str, Any]:
    """Plan hypotheses / analytical approach from DE structure — before DA writes SQL."""
    theme_id = _theme_id(state)
    theme = _state_get(state, "theme", "")
    skill = load_agent_skill("data_scientist")
    state_with_handoff = {
        "theme": theme,
        "theme_id": theme_id,
        "discovery_context": _state_get(state, "discovery_context", ""),
        "knowledge_context": _state_get(state, "knowledge_context", ""),
        "sql_reference_context": _state_get(state, "sql_reference_context", ""),
        "ceo_feedback_context": _state_get(state, "ceo_feedback_context", ""),
        "prior_handoffs": _state_get(state, "schema_info", ""),
    }
    ctx = _base_context(state_with_handoff)
    prompt = f"""{skill}

Onboarding planning — use DE structure to propose analytical hypotheses BEFORE SQL is written.
Suggest approach, grain risks, sanity checks the analyst should bake into SQL, confidence.

Return:
1) HANDOFF: Thai guidance for Data Analyst (hypotheses, approach, risks to watch)
2) JSON:
{{"hypotheses":[""],"approach_th":"","sanity_checks":[""],"risks":[""],"confidence":"high|medium|low","recommended_validations":[""]}}

{ctx}

Data Engineer handoff:
{_state_get(state, 'schema_info', '(none)')[:1500]}"""
    content = await _invoke_role("data_scientist", prompt, "Complete DS onboarding — approach planning.")
    artifact = _parse_json_block(content)
    handoff = content.split("{")[0].replace("HANDOFF:", "").strip()[:2000] or content[:2000]

    update_role_artifact(
        theme_id,
        "data_scientist",
        handoff_summary=handoff,
        artifact=artifact,
        theme_name=theme,
    )
    role_artifacts = dict(_state_get(state, "role_artifacts", {}) or {})
    role_artifacts["data_scientist"] = artifact
    return {
        "analysis_summary": handoff,
        "role_artifacts": role_artifacts,
        "messages": [AIMessage(content=handoff, name="data_scientist")],
        "current_agent": "data_scientist",
    }


async def onboarding_da_node(state: Any) -> dict[str, Any]:
    theme_id = _theme_id(state)
    theme = _state_get(state, "theme", "")
    skill = load_agent_skill("data_analyst")
    prior = f"{_state_get(state, 'schema_info', '')}\n\n{_state_get(state, 'analysis_summary', '')}"
    state_with_handoff = {
        "theme": theme,
        "theme_id": theme_id,
        "discovery_context": _state_get(state, "discovery_context", ""),
        "knowledge_context": _state_get(state, "knowledge_context", ""),
        "sql_reference_context": _state_get(state, "sql_reference_context", ""),
        "ceo_feedback_context": _state_get(state, "ceo_feedback_context", ""),
        "prior_handoffs": prior,
    }
    ctx = _base_context(state_with_handoff)
    prompt = f"""{skill}

Onboarding task — propose measurable metrics and candidate SQL using ONLY columns from context.
Follow Data Scientist guidance (hypotheses / sanity checks) when shaping SQL.
Do NOT use raw SAP names (FKDAT, NETWR) unless they appear in discovery.

Return:
1) HANDOFF: Thai summary for Business Analyst (metrics, SQL approach, assumptions)
2) JSON:
{{"metric_candidates":[{{"name_th":"","definition_th":"","tables":[],"columns":[]}}],"sample_sql":"","assumptions":[""]}}

{ctx}

Data Engineer handoff:
{_state_get(state, 'schema_info', '(none)')[:1200]}

Data Scientist guidance:
{_state_get(state, 'analysis_summary', '(none)')[:1200]}"""
    content = await _invoke_role("data_analyst", prompt, "Complete DA onboarding — metric candidates.")
    artifact = _parse_json_block(content)
    handoff = content.split("{")[0].replace("HANDOFF:", "").strip()[:2000] or content[:2000]

    update_role_artifact(
        theme_id,
        "data_analyst",
        handoff_summary=handoff,
        artifact=artifact,
        theme_name=theme,
    )
    role_artifacts = dict(_state_get(state, "role_artifacts", {}) or {})
    role_artifacts["data_analyst"] = artifact
    return {
        "query_result": handoff,
        "role_artifacts": role_artifacts,
        "messages": [AIMessage(content=handoff, name="data_analyst")],
        "current_agent": "data_analyst",
    }


async def onboarding_ba_node(state: Any) -> dict[str, Any]:
    theme_id = _theme_id(state)
    theme = _state_get(state, "theme", "")
    skill = load_agent_skill("business_analyst")
    ctx = _base_context(state)
    prompt = f"""{skill}

Onboarding — draft business definitions for CEO review BEFORE any question is asked.

Return:
1) HANDOFF: Executive Thai summary (team baseline for this theme)
2) JSON:
{{"metric_definitions":[{{"name_th":"","definition_th":"","status":"draft"}}],"kpi_targets":[""],"ceo_questions":[""],"recommended_primary_table":"","so_what_th":""}}

{ctx}

Full team context:
DE: {_state_get(state, 'schema_info', '')[:800]}
DS: {_state_get(state, 'analysis_summary', '')[:800]}
DA: {_state_get(state, 'query_result', '')[:800]}"""
    content = await _invoke_role("business_analyst", prompt, "Complete BA onboarding definitions.")
    artifact = _parse_json_block(content)
    handoff = content.split("{")[0].replace("HANDOFF:", "").strip()[:2000] or content[:2000]

    update_role_artifact(
        theme_id,
        "business_analyst",
        handoff_summary=handoff,
        artifact=artifact,
        theme_name=theme,
    )
    role_artifacts = dict(_state_get(state, "role_artifacts", {}) or {})
    role_artifacts["business_analyst"] = artifact
    return {
        "ba_summary": handoff,
        "role_artifacts": role_artifacts,
        "messages": [AIMessage(content=handoff, name="business_analyst")],
        "current_agent": "business_analyst",
    }


async def onboarding_finalize_node(state: Any) -> dict[str, Any]:
    from backend.app.services.team_memory_store import finalize_team_memory

    theme_id = _theme_id(state)
    artifacts = _state_get(state, "role_artifacts", {}) or {}
    ba = artifacts.get("business_analyst", {}) or {}
    de = artifacts.get("data_engineer", {}) or {}
    da = artifacts.get("data_analyst", {}) or {}

    recommended = de.get("primary_tables") or []
    primary = ba.get("recommended_primary_table")
    if primary and primary not in recommended:
        recommended = [primary] + list(recommended)

    metrics = [m.get("name_th", "") for m in ba.get("metric_definitions", []) if m.get("name_th")]
    if not metrics:
        metrics = [m.get("name_th", "") for m in da.get("metric_candidates", []) if m.get("name_th")]

    team_summary = (
        _state_get(state, "ba_summary")
        or _state_get(state, "analysis_summary")
        or "Onboarding completed."
    )

    finalize_team_memory(
        theme_id,
        team_summary=str(team_summary)[:3000],
        recommended_tables=[str(t) for t in recommended[:8]],
        key_metrics=[str(m) for m in metrics[:8]],
        status="completed",
    )
    return {"status": "completed", "team_summary": team_summary}
