"""Background execution for long-running chat / onboarding jobs.

POST endpoints create a job row and an asyncio.Task, then return immediately;
the UI polls /api/v1/jobs/{id}. Runs the LangGraph pipeline via astream so
each agent's output is persisted the moment it finishes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage

from backend.app.agents.orchestrator import graph
from backend.app.agents.state import AgentState
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services import chat_store, consultant_service, job_store
from backend.app.services.chat_lock import thread_lock
from backend.app.services.onboarding_service import run_onboarding

# Strong references so pending tasks are never garbage-collected.
_tasks: dict[str, asyncio.Task] = {}

# Message `name`s that count as team-member output worth persisting mid-run.
_AGENT_ROLES = {"data_engineer", "data_analyst", "data_scientist", "business_analyst"}


class JobConflictError(RuntimeError):
    """A queued/running job already exists for this thread."""

    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        super().__init__("A job is already active for this thread")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _track(job_id: str, task: asyncio.Task) -> None:
    _tasks[job_id] = task

    def _done(t: asyncio.Task) -> None:
        _tasks.pop(job_id, None)
        if not t.cancelled() and t.exception() is not None:
            logger.error("Job %s task raised unexpectedly: %s", job_id, t.exception())

    task.add_done_callback(_done)


def cancel_job(job_id: str) -> bool:
    task = _tasks.get(job_id)
    if task is not None and not task.done():
        task.cancel()
        return True
    return False


def _next_step(node: str, update: dict[str, Any], mode: str) -> str | None:
    """Predict the successor node so the UI can show who is working now."""
    if node == "prepare_context":
        return "de_context" if mode == "explore" else "router"
    if node == "router":
        return update.get("next_agent") or "data_analyst"
    if node == "data_analyst":
        if update.get("sql_error") and not update.get("sql_failed"):
            return "data_analyst"
        return "explore_critique" if mode == "explore" else "summarize"
    return {
        "de_context": "data_analyst",
        "explore_critique": "business_analyst",
        "business_analyst": "quality_assembly",
        "quality_assembly": "summarize",
        "data_engineer": "summarize",
        "data_scientist": "summarize",
        "approval_gate": "summarize",
    }.get(node)


def _record_step(job_id: str, node: str, update: dict[str, Any], mode: str) -> None:
    errors = update.get("step_errors") or []
    status = "failed" if errors else "done"
    note = "; ".join(str(e) for e in errors) if errors else None
    job_store.finish_step(job_id, node, status, note)
    job_store.update_job(job_id, current_step=_next_step(node, update, mode))


def _persist_new_messages(request: ChatRequest, messages: list[Any], already_seen: int) -> int:
    """Persist the yet-unseen tail of the accumulated message list.

    Runs on every `values` snapshot; because the state's message list only
    grows, a snapshot missed for any reason is recovered by the next one.
    """
    for message in messages[already_seen:]:
        if getattr(message, "type", "") != "ai":
            continue
        name = getattr(message, "name", None)
        content = getattr(message, "content", None)
        if name in _AGENT_ROLES and content:
            chat_store.add_message(
                request.thread_id,
                role="assistant",
                content=str(content),
                agent=name,
                mode=request.mode,
                theme=request.theme,
            )
    return len(messages)


def start_chat_job(request: ChatRequest) -> dict[str, Any]:
    existing = job_store.find_active_job("chat", request.thread_id)
    if existing is not None:
        raise JobConflictError(existing)

    job = job_store.create_job(
        "chat",
        request.thread_id,
        question=request.message,
        params={"mode": request.mode, "theme": request.theme, "theme_id": request.theme_id},
    )
    _track(job["id"], asyncio.create_task(_run_chat_job(job["id"], request)))
    return job


def _build_chat_result(
    request: ChatRequest,
    state: AgentState,
    *,
    consultant_note: str | None = None,
) -> dict[str, Any]:
    """Final answer/approval handling — same behavior the old synchronous route had."""
    if state.requires_approval:
        chat_store.add_message(
            request.thread_id,
            role="assistant",
            content=state.schema_info,
            agent=state.current_agent,
            mode=request.mode,
            theme=request.theme,
        )
        return ChatResponse(
            thread_id=request.thread_id,
            agent=state.current_agent,
            content=state.schema_info,
            requires_approval=True,
            pending_action="semantic_layer_update",
        ).model_dump()

    answer = state.final_answer or state.query_result or state.ba_summary or ""
    if not answer.strip():
        answer = (
            "[ไม่มีข้อความตอบจาก agent — ลองใช้ Explore mode และเลือก theme ที่มี CE1SATG ก่อนถามใหม่]"
        )
    quality_payload = state.quality_payload or None
    quality_gaps = quality_payload.get("quality_gaps") if quality_payload else None
    agents_involved = quality_payload.get("agents_involved", []) if quality_payload else []
    display_agent = "ai_data_team" if len(agents_involved) >= 2 else state.current_agent

    chat_store.add_message(
        request.thread_id,
        role="assistant",
        content=answer,
        agent=display_agent,
        mode=request.mode,
        theme=request.theme,
    )

    content = answer
    if consultant_note:
        chat_store.add_message(
            request.thread_id,
            role="assistant",
            content=consultant_note,
            agent="consultant",
            mode=request.mode,
            theme=request.theme,
        )
        content = (
            answer
            + "\n\n---\n### 🎓 ความเห็นที่ปรึกษา (Claude)\n"
            + consultant_note
        )

    return ChatResponse(
        thread_id=request.thread_id,
        agent=display_agent,
        content=content,
        agents_involved=agents_involved,
        requires_approval=False,
        quality_payload=quality_payload,
        quality_gaps=quality_gaps,
    ).model_dump()


async def _stream_chat_graph(job_id: str, request: ChatRequest) -> AgentState:
    """Run the LangGraph stream and return the final AgentState."""
    config = {"configurable": {"thread_id": request.thread_id}}
    input_state = AgentState(
        messages=[HumanMessage(content=request.message)],
        thread_id=request.thread_id,
        mode=request.mode,
        theme=request.theme or "",
        theme_id=request.theme_id or "",
    )
    job_store.update_job(job_id, current_step="prepare_context")

    # Two stream modes: `updates` drives the step timeline (node names),
    # `values` drives message persistence. Persisting from cumulative
    # `values` snapshots is self-healing — per-step update payloads
    # proved unreliable under long node latencies.
    persisted_count = 0
    async for stream_mode_name, chunk in graph.astream(
        input_state.model_dump(), config=config, stream_mode=["updates", "values"]
    ):
        if stream_mode_name == "updates" and isinstance(chunk, dict):
            for node_name, raw_update in chunk.items():
                parts = raw_update if isinstance(raw_update, list) else [raw_update]
                update: dict[str, Any] = {}
                for part in parts:
                    if isinstance(part, dict):
                        update.update(part)
                _record_step(job_id, node_name, update, request.mode)
        elif stream_mode_name == "values" and isinstance(chunk, dict):
            persisted_count = _persist_new_messages(
                request, chunk.get("messages") or [], persisted_count
            )

    snapshot = await graph.aget_state(config)
    return AgentState(**snapshot.values)


async def _run_chat_job(job_id: str, request: ChatRequest) -> None:
    try:
        async with thread_lock(request.thread_id):
            job_store.update_job(job_id, status="running", started_at=_utc_now())
            logger.info(
                "Chat job %s started: thread=%s mode=%s message=%s...",
                job_id,
                request.thread_id,
                request.mode,
                request.message[:80],
            )

            chat_store.add_message(
                request.thread_id,
                role="user",
                content=request.message,
                mode=request.mode,
                theme=request.theme,
            )

            max_seconds = get_settings().chat_job_max_seconds
            try:
                state = await asyncio.wait_for(
                    _stream_chat_graph(job_id, request),
                    timeout=max_seconds,
                )
            except asyncio.TimeoutError:
                msg = (
                    f"Chat job exceeded wall-clock limit "
                    f"({max_seconds}s) — งานถูกหยุดเพื่อไม่ให้ค้าง"
                )
                logger.error("Chat job %s timed out after %ss", job_id, max_seconds)
                job = job_store.get_job(job_id)
                if job and job.get("current_step"):
                    job_store.finish_step(job_id, job["current_step"], "failed", msg)
                job_store.update_job(
                    job_id,
                    status="failed",
                    error=msg,
                    current_step=None,
                    finished_at=_utc_now(),
                )
                return

            consultant_note = None
            if not state.requires_approval and consultant_service.should_review(state):
                job_store.append_step(job_id, "consultant_review")
                consultant_note = await consultant_service.review_answer(
                    request.theme_id or "",
                    request.theme or "",
                    request.message,
                    draft_answer=state.final_answer
                    or state.query_result
                    or state.ba_summary
                    or "",
                    quality_payload=state.quality_payload or {},
                    step_errors=state.step_errors,
                )
                job_store.finish_step(
                    job_id,
                    "consultant_review",
                    "done" if consultant_note else "failed",
                    None if consultant_note else "consultant unavailable — skipped",
                )
            result = _build_chat_result(request, state, consultant_note=consultant_note)
            job_store.update_job(
                job_id,
                status="done",
                result=result,
                current_step=None,
                finished_at=_utc_now(),
            )
            logger.info("Chat job %s done", job_id)
    except asyncio.CancelledError:
        job_store.update_job(
            job_id,
            status="cancelled",
            error="Job was cancelled",
            current_step=None,
            finished_at=_utc_now(),
        )
        raise
    except Exception as e:
        logger.exception("Chat job %s failed", job_id)
        job = job_store.get_job(job_id)
        if job and job.get("current_step"):
            job_store.finish_step(job_id, job["current_step"], "failed", str(e))
        job_store.update_job(
            job_id,
            status="failed",
            error=f"{type(e).__name__}: {e}",
            current_step=None,
            finished_at=_utc_now(),
        )


def start_onboarding_job(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    existing = job_store.find_active_job("onboarding", theme_id)
    if existing is not None:
        raise JobConflictError(existing)

    job = job_store.create_job(
        "onboarding",
        theme_id,
        question=theme_name or theme_id,
        params={"theme_name": theme_name},
    )
    _track(job["id"], asyncio.create_task(_run_onboarding_job(job["id"], theme_id, theme_name)))
    return job


async def _run_onboarding_job(job_id: str, theme_id: str, theme_name: str) -> None:
    try:
        job_store.update_job(job_id, status="running", started_at=_utc_now())
        job_store.append_step(job_id, "onboarding")
        result = await run_onboarding(theme_id, theme_name)
        job_store.finish_step(job_id, "onboarding", "done")

        if consultant_service.is_enabled("coach_onboarding"):
            job_store.append_step(job_id, "consultant_coach")
            coach = await consultant_service.coach_team(theme_id, theme_name)
            job_store.finish_step(
                job_id,
                "consultant_coach",
                "done" if coach else "failed",
                None if coach else "consultant unavailable — skipped",
            )
            if coach:
                result["consultant_coach"] = coach

        job_store.update_job(
            job_id,
            status="done",
            result=result,
            current_step=None,
            finished_at=_utc_now(),
        )
        logger.info("Onboarding job %s done theme=%s", job_id, theme_id)
    except asyncio.CancelledError:
        job_store.update_job(
            job_id,
            status="cancelled",
            error="Job was cancelled",
            current_step=None,
            finished_at=_utc_now(),
        )
        raise
    except Exception as e:
        logger.exception("Onboarding job %s failed theme=%s", job_id, theme_id)
        job_store.finish_step(job_id, "onboarding", "failed", str(e))
        job_store.update_job(
            job_id,
            status="failed",
            error=f"{type(e).__name__}: {e}",
            current_step=None,
            finished_at=_utc_now(),
        )


def start_consult_job(theme_id: str, question: str) -> dict[str, Any]:
    existing = job_store.find_active_job("consult", theme_id)
    if existing is not None:
        raise JobConflictError(existing)

    job = job_store.create_job(
        "consult",
        theme_id,
        question=question,
        params={"theme_id": theme_id},
    )
    _track(job["id"], asyncio.create_task(_run_consult_job(job["id"], theme_id, question)))
    return job


async def _run_consult_job(job_id: str, theme_id: str, question: str) -> None:
    try:
        job_store.update_job(job_id, status="running", started_at=_utc_now())
        job_store.append_step(job_id, "consult")
        advice = await consultant_service.answer_question(theme_id, question)
        if advice is None:
            job_store.finish_step(job_id, "consult", "failed", "Consultant unavailable")
            job_store.update_job(
                job_id,
                status="failed",
                error="Consultant unavailable — ตรวจสอบ ANTHROPIC_API_KEY / เครือข่าย",
                current_step=None,
                finished_at=_utc_now(),
            )
            return

        job_store.finish_step(job_id, "consult", "done")
        job_store.update_job(
            job_id,
            status="done",
            result={"advice": advice, "theme_id": theme_id},
            current_step=None,
            finished_at=_utc_now(),
        )
        logger.info("Consult job %s done theme=%s", job_id, theme_id)
    except asyncio.CancelledError:
        job_store.update_job(
            job_id,
            status="cancelled",
            error="Job was cancelled",
            current_step=None,
            finished_at=_utc_now(),
        )
        raise
    except Exception as e:
        logger.exception("Consult job %s failed theme=%s", job_id, theme_id)
        job_store.finish_step(job_id, "consult", "failed", str(e))
        job_store.update_job(
            job_id,
            status="failed",
            error=f"{type(e).__name__}: {e}",
            current_step=None,
            finished_at=_utc_now(),
        )
