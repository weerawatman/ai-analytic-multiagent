"""Onboarding nodes — each role does homework before CEO asks questions."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.team_memory_store import update_role_artifact

settings = get_settings()


def _llm() -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=0.1,
        timeout=settings.ollama_timeout,
    )


def _parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


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
        logger.error("Onboarding %s failed: %s", role, exc)
        return f"[Onboarding error for {role}] {exc}"


def _base_context(state: dict[str, Any]) -> str:
    parts = [
        f"Theme: {state.get('theme', '')} (id={state.get('theme_id', '')})",
        f"\nDiscovery:\n{state.get('discovery_context', '(none)')[:3500]}",
        f"\nKnowledge:\n{state.get('knowledge_context', '(none)')[:2000]}",
        f"\nSQL Reference:\n{state.get('sql_reference_context', '(none)')[:2000]}",
    ]
    prior = state.get("prior_handoffs", "")
    if prior:
        parts.append(f"\nPrior team handoffs:\n{prior[:2500]}")
    feedback = state.get("ceo_feedback_context", "")
    if feedback:
        parts.append(f"\nCEO feedback:\n{feedback[:1500]}")
    return "\n".join(parts)


async def onboarding_de_node(state: dict[str, Any]) -> dict[str, Any]:
    theme_id = state["theme_id"]
    theme = state.get("theme", "")
    skill = load_agent_skill("data_engineer")
    ctx = _base_context(state)
    prompt = f"""{skill}

You are onboarding this theme BEFORE the CEO asks questions.
Analyze structure, grain, keys, relationships, and data quality flags.

Return TWO parts:
1) HANDOFF: Thai summary (max 400 words) for the Data Analyst
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
    return {
        "schema_info": handoff,
        "role_artifacts": {**state.get("role_artifacts", {}), "data_engineer": artifact},
        "messages": [AIMessage(content=handoff, name="data_engineer")],
        "current_agent": "data_engineer",
    }


async def onboarding_da_node(state: dict[str, Any]) -> dict[str, Any]:
    theme_id = state["theme_id"]
    theme = state.get("theme", "")
    skill = load_agent_skill("data_analyst")
    state_with_handoff = {**state, "prior_handoffs": state.get("schema_info", "")}
    ctx = _base_context(state_with_handoff)
    prompt = f"""{skill}

Onboarding task — propose measurable metrics and candidate SQL using ONLY columns from context.
Do NOT use raw SAP names (FKDAT, NETWR) unless they appear in discovery.

Return:
1) HANDOFF: Thai summary for Data Scientist (metrics, SQL approach, assumptions)
2) JSON:
{{"metric_candidates":[{{"name_th":"","definition_th":"","tables":[],"columns":[]}}],"sample_sql":"","assumptions":[""]}}

{ctx}

Data Engineer handoff:
{state.get('schema_info', '(none)')[:1500]}"""
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
    return {
        "query_result": handoff,
        "role_artifacts": {**state.get("role_artifacts", {}), "data_analyst": artifact},
        "messages": [AIMessage(content=handoff, name="data_analyst")],
        "current_agent": "data_analyst",
    }


async def onboarding_ds_node(state: dict[str, Any]) -> dict[str, Any]:
    theme_id = state["theme_id"]
    theme = state.get("theme", "")
    skill = load_agent_skill("data_scientist")
    prior = f"{state.get('schema_info', '')}\n\n{state.get('query_result', '')}"
    state_with_handoff = {**state, "prior_handoffs": prior}
    ctx = _base_context(state_with_handoff)
    prompt = f"""{skill}

Onboarding critique — review DE structure and DA metric proposals.
Flag sanity checks, risks, confidence level.

Return:
1) HANDOFF: Thai critique for Business Analyst
2) JSON:
{{"sanity_checks":[""],"risks":[""],"confidence":"high|medium|low","recommended_validations":[""]}}

{ctx}

Analyst handoff:
{state.get('query_result', '(none)')[:1500]}"""
    content = await _invoke_role("data_scientist", prompt, "Complete DS onboarding critique.")
    artifact = _parse_json_block(content)
    handoff = content.split("{")[0].replace("HANDOFF:", "").strip()[:2000] or content[:2000]

    update_role_artifact(
        theme_id,
        "data_scientist",
        handoff_summary=handoff,
        artifact=artifact,
        theme_name=theme,
    )
    return {
        "analysis_summary": handoff,
        "role_artifacts": {**state.get("role_artifacts", {}), "data_scientist": artifact},
        "messages": [AIMessage(content=handoff, name="data_scientist")],
        "current_agent": "data_scientist",
    }


async def onboarding_ba_node(state: dict[str, Any]) -> dict[str, Any]:
    theme_id = state["theme_id"]
    theme = state.get("theme", "")
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
DE: {state.get('schema_info', '')[:800]}
DA: {state.get('query_result', '')[:800]}
DS: {state.get('analysis_summary', '')[:800]}"""
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
    return {
        "ba_summary": handoff,
        "role_artifacts": {**state.get("role_artifacts", {}), "business_analyst": artifact},
        "messages": [AIMessage(content=handoff, name="business_analyst")],
        "current_agent": "business_analyst",
    }


async def onboarding_finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    from backend.app.services.team_memory_store import finalize_team_memory

    theme_id = state["theme_id"]
    artifacts = state.get("role_artifacts", {})
    ba = artifacts.get("business_analyst", {})
    de = artifacts.get("data_engineer", {})
    da = artifacts.get("data_analyst", {})

    recommended = de.get("primary_tables") or []
    primary = ba.get("recommended_primary_table")
    if primary and primary not in recommended:
        recommended = [primary] + list(recommended)

    metrics = [m.get("name_th", "") for m in ba.get("metric_definitions", []) if m.get("name_th")]
    if not metrics:
        metrics = [m.get("name_th", "") for m in da.get("metric_candidates", []) if m.get("name_th")]

    team_summary = state.get("ba_summary") or state.get("analysis_summary") or "Onboarding completed."

    finalize_team_memory(
        theme_id,
        team_summary=team_summary[:3000],
        recommended_tables=[str(t) for t in recommended[:8]],
        key_metrics=[str(m) for m in metrics[:8]],
        status="completed",
    )
    return {"status": "completed", "team_summary": team_summary}
