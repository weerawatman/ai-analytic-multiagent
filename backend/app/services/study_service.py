"""Nightly study session orchestration (Phase K).

Picks 1–2 curriculum questions per enabled role (or round-robin one role),
runs them through an injectable answer function (production: chat graph),
records curriculum attempts + team-memory pending CEO approve, and grades
against a matched golden question when available.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services import curriculum_store, eval_service

AnswerFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def _default_graph_answer(question: dict[str, Any]) -> dict[str, Any]:
    """Run one curriculum question through the normal chat graph."""
    from langchain_core.messages import HumanMessage

    from backend.app.agents.orchestrator import graph
    from backend.app.agents.state import AgentState

    theme_id = question.get("theme_id") or "sales"
    theme = question.get("theme") or theme_id
    thread_id = f"study:{question.get('role')}:{question.get('id')}"
    t0 = time.perf_counter()
    input_state = AgentState(
        messages=[HumanMessage(content=question["question_th"])],
        thread_id=thread_id,
        mode="explore",
        theme=theme,
        theme_id=theme_id,
    )
    config = {"configurable": {"thread_id": thread_id}}
    final: dict[str, Any] = {}
    async for _mode, chunk in graph.astream(
        input_state.model_dump(), config=config, stream_mode=["values"]
    ):
        if isinstance(chunk, dict):
            final = chunk
    state = (
        AgentState(**final)
        if final
        else AgentState(messages=[], thread_id=thread_id, mode="explore")
    )
    answer = state.final_answer or state.query_result or state.ba_summary or ""
    sql_ok = bool(state.query_result) and not bool(state.step_errors)
    return {
        "answer": answer,
        "sql_ok": sql_ok,
        "latency_s": time.perf_counter() - t0,
        "quality_payload": state.quality_payload or {},
    }


async def run_study_session(
    *,
    theme_id: str = "sales",
    theme_name: str = "",
    roles: list[str] | None = None,
    questions_per_role: int | None = None,
    answer_fn: AnswerFn | None = None,
) -> dict[str, Any]:
    """Study 1–2 due questions; safe to call offline with a mock ``answer_fn``."""
    settings = get_settings()
    n = questions_per_role if questions_per_role is not None else settings.study_questions_per_run
    n = max(1, min(n, 2))
    role_list = roles or list(curriculum_store.ROLES)
    curriculum_store.ensure_all_curricula()
    answer = answer_fn or _default_graph_answer
    goldens = eval_service.load_golden_questions(active_only=True)

    studied: list[dict[str, Any]] = []
    for role in role_list:
        due = curriculum_store.pick_due_questions(role, n=n)
        for q in due:
            payload = {
                **q,
                "role": role,
                "theme_id": theme_id,
                "theme": theme_name or theme_id,
            }
            try:
                result = await answer(payload)
            except Exception as exc:
                logger.warning("Study answer failed %s/%s: %s", role, q.get("id"), type(exc).__name__)
                result = {
                    "answer": f"[study error: {type(exc).__name__}]",
                    "sql_ok": False,
                    "latency_s": 0.0,
                }

            answer_text = str(result.get("answer") or "")
            golden = curriculum_store.match_golden_question(q, goldens)
            passed: bool | None = None
            golden_match: dict[str, Any] | None = None
            if golden is not None:
                grade = eval_service.grade_answer(
                    golden,
                    answer_text=answer_text,
                    reference_value=None,  # numeric ref needs live SQL; keyword/sql soft
                    sql_ok=bool(result.get("sql_ok", False)),
                    latency_s=float(result.get("latency_s") or 0.0),
                )
                # Without live reference, pass on keywords + sql_ok when keywords exist
                keywords = list(golden.get("expected_keywords_th") or [])
                if keywords:
                    passed = bool(grade.get("keywords_ok") and result.get("sql_ok", False))
                else:
                    passed = bool(result.get("sql_ok", False))
                golden_match = {
                    "golden_question_id": golden.get("id"),
                    "passed": passed,
                    "keywords_ok": grade.get("keywords_ok"),
                }

            curriculum_store.record_attempt(
                role,
                q["id"],
                answer_excerpt=answer_text,
                passed=passed,
                golden_match=golden_match,
            )
            memory = curriculum_store.append_study_result_to_memory(
                theme_id,
                role=role,
                curriculum_question_id=q["id"],
                question_th=q.get("question_th") or "",
                answer_excerpt=answer_text,
                golden_match=golden_match,
                theme_name=theme_name,
            )
            studied.append(
                {
                    "role": role,
                    "question_id": q["id"],
                    "passed": passed,
                    "golden_match": golden_match,
                    "memory_status": "pending_ceo_approve",
                    "study_result_id": (memory.get("study_results") or [{}])[-1].get("id"),
                }
            )

    return {
        "theme_id": theme_id,
        "studied_count": len(studied),
        "studied": studied,
        "pass_rates": curriculum_store.pass_rate_summary(),
    }
