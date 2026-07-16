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
from backend.app.core.logger import logger
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services import chat_store, job_store
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


def _build_chat_result(request: ChatRequest, state: AgentState) -> dict[str, Any]:
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

    return ChatResponse(
        thread_id=request.thread_id,
        agent=display_agent,
        content=answer,
        agents_involved=agents_involved,
        requires_approval=False,
        quality_payload=quality_payload,
        quality_gaps=quality_gaps,
    ).model_dump()


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
            state = AgentState(**snapshot.values)
            result = _build_chat_result(request, state)
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
