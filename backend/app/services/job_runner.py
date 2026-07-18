"""Background execution for long-running chat / onboarding jobs.

POST endpoints create a job row and an asyncio.Task, then return immediately;
the UI polls /api/v1/jobs/{id}. Runs the LangGraph pipeline via astream so
each agent's output is persisted the moment it finishes.
"""

from __future__ import annotations

import asyncio
import re
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
from backend.app.services.error_sanitizer import sanitize_step_errors
from backend.app.services.onboarding_service import run_onboarding

# Strong references so pending tasks are never garbage-collected.
_tasks: dict[str, asyncio.Task] = {}

# Message `name`s that count as team-member output worth persisting mid-run.
_AGENT_ROLES = {"data_engineer", "data_analyst", "data_scientist", "business_analyst"}

# Failed-attempt marker lines carry technical detail (`ExceptionType: detail`,
# ODBC text) that must never reach persisted chat history.
_SQL_ATTEMPT_FAILED_LINE = re.compile(r"^SQL_ATTEMPT_FAILED:.*$", re.MULTILINE)


def _sanitize_agent_content(name: str, content: str) -> str:
    """Strip technical SQL-failure text before persisting mid-stream messages.

    data_analyst failure attempts accumulate `SQL_ATTEMPT_FAILED: ...` lines;
    each is replaced with a short polite Thai note numbered per attempt, while
    the analytic portion and the final graceful summary stay intact.
    """
    if name != "data_analyst" or "SQL_ATTEMPT_FAILED" not in content:
        return content
    attempt = 0

    def _replace(_match: re.Match[str]) -> str:
        nonlocal attempt
        attempt += 1
        return f"[รอบที่ {attempt}] SQL ยังไม่ผ่าน — ทีมกำลังปรับและลองใหม่"

    return _SQL_ATTEMPT_FAILED_LINE.sub(_replace, content)


class JobConflictError(RuntimeError):
    """A queued/running job already exists for this thread."""

    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        super().__init__("A job is already active for this thread")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail_job_on_timeout(job_id: str, max_seconds: int) -> None:
    """Mark a job failed after its wall-clock budget with a polite Thai error."""
    msg = (
        f"งานใช้เวลาเกินกำหนด {max_seconds} วินาที ระบบจึงหยุดงานเพื่อไม่ให้ค้าง "
        "— กรุณาลองใหม่ หรือปรับคำถามให้แคบลง (เกินเวลาที่กำหนดของงาน)"
    )
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


def _fail_job_on_error(job_id: str, e: BaseException) -> None:
    """Mark a job failed keeping only the exception type user-facing.

    Full detail is already in backend.log via logger.exception at the caller;
    the job error/note surfaces directly in chat and the progress UI.
    """
    friendly = (
        f"เกิดข้อผิดพลาดระหว่างทำงาน ({type(e).__name__}) "
        "— รายละเอียดอยู่ใน data/local/logs/backend.log"
    )
    job = job_store.get_job(job_id)
    if job and job.get("current_step"):
        job_store.finish_step(
            job_id,
            job["current_step"],
            "failed",
            f"ขั้นตอนนี้ทำงานไม่สำเร็จ ({type(e).__name__})",
        )
    job_store.update_job(
        job_id,
        status="failed",
        error=friendly,
        current_step=None,
        finished_at=_utc_now(),
    )


def _track(job_id: str, task: asyncio.Task) -> None:
    _tasks[job_id] = task

    def _done(t: asyncio.Task) -> None:
        _tasks.pop(job_id, None)
        if not t.cancelled() and t.exception() is not None:
            logger.error("Job %s task raised unexpectedly: %s", job_id, t.exception())

    task.add_done_callback(_done)


# Phase G1 — heartbeat ticker lives on the runner (not inside graph nodes)
# so the pulse continues even while awaiting a long LLM call.
_HEARTBEAT_INTERVAL_S = 10.0


async def _heartbeat_loop(job_id: str) -> None:
    try:
        while True:
            job_store.touch_job(job_id)
            await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
    except asyncio.CancelledError:
        raise


def _mark_job_running(job_id: str) -> None:
    now = _utc_now()
    job_store.update_job(job_id, status="running", started_at=now, heartbeat_at=now)


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
    if node == "de_context":
        return "explore_critique"
    if node == "explore_critique":
        # Pre-SQL plan (no query_result yet) → DA; post-SQL critique → BA.
        if update.get("query_result"):
            return "business_analyst"
        # When DS only returns analysis_summary (plan), go to DA.
        return "data_analyst"
    if node == "data_analyst":
        if update.get("sql_error") and not update.get("sql_failed"):
            return "data_analyst"
        return "business_analyst" if mode == "explore" else "summarize"
    return {
        "business_analyst": "quality_assembly",
        "quality_assembly": "summarize",
        "data_engineer": "summarize",
        "data_scientist": "summarize",
        "approval_gate": "summarize",
    }.get(node)


def _record_step(job_id: str, node: str, update: dict[str, Any], mode: str) -> None:
    errors = update.get("step_errors") or []
    status = "failed" if errors else "done"
    note = None
    if errors:
        # Full detail stays in the log + step_errors state; the persisted note
        # is rendered directly in the progress UI, so keep it polite/clean.
        logger.warning("Job %s step %s errors: %s", job_id, node, errors)
        note = "; ".join(sanitize_step_errors(errors))
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
                content=_sanitize_agent_content(name, str(content)),
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


def _last_human_content(messages: list[Any]) -> str:
    for message in reversed(messages or []):
        if getattr(message, "type", "") == "human":
            return str(getattr(message, "content", ""))
    return ""


async def _partial_state_for(request: ChatRequest) -> AgentState | None:
    """Checkpointed state for this thread, only if it belongs to this question.

    The MemorySaver checkpoint survives per-node completions, so even after a
    wall-clock timeout the finished agents' output is recoverable. A snapshot
    from a *previous* question (timeout before the first checkpoint of this
    run) must never leak into this answer — hence the last-human-message guard.
    """
    try:
        snapshot = await graph.aget_state({"configurable": {"thread_id": request.thread_id}})
        values = getattr(snapshot, "values", None) or {}
    except Exception:
        logger.exception("Partial-state recovery failed for thread %s", request.thread_id)
        return None
    if not values:
        return None
    state = AgentState(**values)
    if _last_human_content(state.messages) != request.message:
        return None
    return state


def build_partial_answer(state: AgentState, max_seconds: int) -> str | None:
    """Deterministic Thai partial answer from whatever agents completed.

    Returns None when there is nothing useful to show (no DE/DS/DA output).
    Never includes raw errors — content fields are already sanitized upstream.
    """
    from backend.app.agents.data_analyst import strip_failed_attempt_lines
    from backend.app.services.quality_assembly import data_source_label_th

    sections: list[str] = []
    if state.schema_info:
        sections.append(f"### 🔧 Data Engineer (เสร็จแล้ว)\n{state.schema_info[:1500]}")
    if state.analysis_summary:
        sections.append(f"### 🧪 Data Scientist (เสร็จแล้ว)\n{state.analysis_summary[:1500]}")
    if state.query_result:
        cleaned = strip_failed_attempt_lines(state.query_result)
        if cleaned:
            sections.append(f"### 📈 Data Analyst (เสร็จแล้ว)\n{cleaned[:1500]}")
    if state.generated_sql and "DRAFT_SQL" not in (state.query_result or ""):
        sections.append(f"### Draft SQL\n```sql\n{state.generated_sql[:1200]}\n```")
    if not sections:
        return None

    header = (
        f"⚠️ **คำตอบบางส่วน** — งานใช้เวลาเกินกำหนด {max_seconds} วินาที "
        "ระบบจึงสรุปเท่าที่ทีมทำเสร็จแล้ว (ไม่ทิ้งงานเปล่า)"
    )
    if state.sql_source in ("fabric", "postgres"):
        header += f"\n\nแหล่งข้อมูล: {data_source_label_th(state.sql_source)}"
    next_action = (
        "### ขั้นตอนถัดไป\n"
        "- ถามซ้ำโดยระบุช่วงเวลา/หน่วยงานให้แคบลง เพื่อให้จบใน 1 รอบ\n"
        "- หรือใช้ Draft SQL ข้างต้นตรวจกับ BA/DA ก่อน promote เป็น Trusted"
    )
    return "\n\n---\n\n".join([header, *sections, next_action])


async def _finish_chat_job_with_partial(
    job_id: str, request: ChatRequest, max_seconds: int
) -> bool:
    """After a wall-clock timeout, ship a partial answer when one exists."""
    state = await _partial_state_for(request)
    partial = build_partial_answer(state, max_seconds) if state else None
    if not partial:
        return False

    chat_store.add_message(
        request.thread_id,
        role="assistant",
        content=partial,
        agent="ai_data_team",
        mode=request.mode,
        theme=request.theme,
    )
    timeout_note = (
        f"งานเกินเวลา {max_seconds} วินาที — ส่งคำตอบบางส่วนจากขั้นตอนที่เสร็จแล้ว"
    )
    job = job_store.get_job(job_id)
    if job and job.get("current_step"):
        job_store.finish_step(job_id, job["current_step"], "failed", timeout_note)
    result = ChatResponse(
        thread_id=request.thread_id,
        agent="ai_data_team",
        content=partial,
        requires_approval=False,
    ).model_dump()
    result["partial"] = True
    job_store.update_job(
        job_id,
        status="done",
        result=result,
        error=None,
        current_step=None,
        finished_at=_utc_now(),
    )
    logger.warning("Chat job %s timed out — shipped partial answer", job_id)
    return True


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
    hb_task: asyncio.Task | None = None
    try:
        async with thread_lock(request.thread_id):
            _mark_job_running(job_id)
            hb_task = asyncio.create_task(_heartbeat_loop(job_id))
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
                logger.error("Chat job %s timed out after %ss", job_id, max_seconds)
                # Reliability contract: never end with a silent blank — if any
                # agent finished, ship its output as a labeled partial answer.
                if await _finish_chat_job_with_partial(job_id, request, max_seconds):
                    return
                _fail_job_on_timeout(job_id, max_seconds)
                return

            consultant_note = None
            if not state.requires_approval and consultant_service.should_review(state):
                job_store.append_step(job_id, "consultant_review")
                # The 1200s wall-clock wait_for above only covers the graph;
                # bound the consultant step separately so a hung Claude call
                # cannot stall the job indefinitely (Phase D review, D4 gap).
                consultant_seconds = get_settings().consultant_timeout + 30
                try:
                    consultant_note = await asyncio.wait_for(
                        consultant_service.review_answer(
                            request.theme_id or "",
                            request.theme or "",
                            request.message,
                            draft_answer=state.final_answer
                            or state.query_result
                            or state.ba_summary
                            or "",
                            quality_payload=state.quality_payload or {},
                            step_errors=state.step_errors,
                        ),
                        timeout=consultant_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Chat job %s consultant review timed out after %ss — skipped",
                        job_id,
                        consultant_seconds,
                    )
                    consultant_note = None
                    job_store.finish_step(
                        job_id,
                        "consultant_review",
                        "failed",
                        f"ขั้นตอนตรวจทานของที่ปรึกษาเกินเวลา ({consultant_seconds} วินาที) — ข้ามขั้นตอนนี้",
                    )
                else:
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
        _fail_job_on_error(job_id, e)
    finally:
        if hb_task is not None:
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass


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


async def _run_deep_profile_steps(job_id: str, theme_id: str, theme_name: str) -> dict[str, Any]:
    """Deterministic homework + starter pack (bounded read-only SQL, no LLM).

    Fail-soft: profiling problems are recorded on the step and must never
    block the rest of the job.
    """
    from backend.app.services.deep_profile_service import build_homework
    from backend.app.services.insight_starter_service import build_starter_pack

    out: dict[str, Any] = {}
    job_store.append_step(job_id, "deep_profile")
    try:
        homework = await asyncio.to_thread(build_homework, theme_id, theme_name)
        out["homework"] = {
            "evidence_level": homework.get("evidence_level"),
            "tables": len(homework.get("table_roles") or {}),
            "dq_issues": len(homework.get("data_quality_issues") or []),
        }
        job_store.finish_step(job_id, "deep_profile", "done")
    except Exception as e:
        logger.exception("Deep profile failed theme=%s", theme_id)
        job_store.finish_step(
            job_id, "deep_profile", "failed", f"ทำ data homework ไม่สำเร็จ ({type(e).__name__})"
        )

    job_store.append_step(job_id, "starter_pack")
    try:
        pack = await asyncio.to_thread(build_starter_pack, theme_id, theme_name)
        validated = sum(
            1 for i in pack.get("items", []) if i.get("evidence_status") == "validated"
        )
        out["starter_pack"] = {"items": len(pack.get("items", [])), "validated": validated}
        job_store.finish_step(job_id, "starter_pack", "done")
    except Exception as e:
        logger.exception("Starter pack failed theme=%s", theme_id)
        job_store.finish_step(
            job_id, "starter_pack", "failed", f"สร้าง insight starter pack ไม่สำเร็จ ({type(e).__name__})"
        )
    return out


async def _run_onboarding_work(job_id: str, theme_id: str, theme_name: str) -> dict[str, Any]:
    # Deterministic evidence first — role LLM handoffs then reference real
    # profiled numbers instead of guessing from table names.
    deep = await _run_deep_profile_steps(job_id, theme_id, theme_name)

    job_store.append_step(job_id, "onboarding")
    result = await run_onboarding(theme_id, theme_name)
    result.update(deep)
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
    return result


async def _run_onboarding_job(job_id: str, theme_id: str, theme_name: str) -> None:
    hb_task: asyncio.Task | None = None
    try:
        _mark_job_running(job_id)
        hb_task = asyncio.create_task(_heartbeat_loop(job_id))
        # Wall-clock cap for the whole job (multiple Ollama roles + coach) —
        # per-call HTTP timeouts alone cannot bound the total (Phase D review).
        max_seconds = get_settings().onboarding_job_max_seconds
        try:
            result = await asyncio.wait_for(
                _run_onboarding_work(job_id, theme_id, theme_name),
                timeout=max_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Onboarding job %s timed out after %ss theme=%s",
                job_id,
                max_seconds,
                theme_id,
            )
            _fail_job_on_timeout(job_id, max_seconds)
            return

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
        _fail_job_on_error(job_id, e)
    finally:
        if hb_task is not None:
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass


def start_deep_onboarding_job(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    """Deterministic deep profiling only (homework + starter pack) — no LLM.

    Cheap enough to re-run on demand from the UI without redoing the full
    LLM onboarding.
    """
    existing = job_store.find_active_job("deep_onboarding", theme_id)
    if existing is not None:
        raise JobConflictError(existing)

    job = job_store.create_job(
        "deep_onboarding",
        theme_id,
        question=theme_name or theme_id,
        params={"theme_name": theme_name},
    )
    _track(job["id"], asyncio.create_task(_run_deep_onboarding_job(job["id"], theme_id, theme_name)))
    return job


async def _run_deep_onboarding_job(job_id: str, theme_id: str, theme_name: str) -> None:
    hb_task: asyncio.Task | None = None
    try:
        _mark_job_running(job_id)
        hb_task = asyncio.create_task(_heartbeat_loop(job_id))
        max_seconds = get_settings().deep_onboarding_max_seconds
        try:
            result = await asyncio.wait_for(
                _run_deep_profile_steps(job_id, theme_id, theme_name),
                timeout=max_seconds,
            )
        except asyncio.TimeoutError:
            logger.error("Deep onboarding job %s timed out after %ss", job_id, max_seconds)
            _fail_job_on_timeout(job_id, max_seconds)
            return

        job_store.update_job(
            job_id,
            status="done",
            result=result,
            current_step=None,
            finished_at=_utc_now(),
        )
        logger.info("Deep onboarding job %s done theme=%s", job_id, theme_id)
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
        logger.exception("Deep onboarding job %s failed theme=%s", job_id, theme_id)
        _fail_job_on_error(job_id, e)
    finally:
        if hb_task is not None:
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass


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
    hb_task: asyncio.Task | None = None
    try:
        _mark_job_running(job_id)
        hb_task = asyncio.create_task(_heartbeat_loop(job_id))
        job_store.append_step(job_id, "consult")
        # Same bound as the consultant review step in _run_chat_job — a hung
        # Claude call must not stall the job past its own HTTP timeout.
        max_seconds = get_settings().consultant_timeout + 30
        try:
            advice = await asyncio.wait_for(
                consultant_service.answer_question(theme_id, question),
                timeout=max_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Consult job %s timed out after %ss theme=%s", job_id, max_seconds, theme_id
            )
            _fail_job_on_timeout(job_id, max_seconds)
            return
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
        _fail_job_on_error(job_id, e)
    finally:
        if hb_task is not None:
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass


def start_snapshot_refresh_job(
    *,
    mode: str = "auto",
    end_month: str | None = None,
    metric_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Enqueue metric snapshot refresh (Phase H) — no LLM, SQL from registry only."""
    thread_id = "analytics:snapshot_refresh"
    existing = job_store.find_active_job("snapshot_refresh", thread_id)
    if existing is not None:
        raise JobConflictError(existing)

    job = job_store.create_job(
        "snapshot_refresh",
        thread_id,
        question=f"snapshot_refresh:{mode}",
        params={
            "mode": mode,
            "end_month": end_month,
            "metric_keys": metric_keys,
        },
    )
    _track(
        job["id"],
        asyncio.create_task(
            _run_snapshot_refresh_job(
                job["id"], mode=mode, end_month=end_month, metric_keys=metric_keys
            )
        ),
    )
    return job


async def _run_snapshot_refresh_job(
    job_id: str,
    *,
    mode: str,
    end_month: str | None,
    metric_keys: list[str] | None,
) -> None:
    from backend.app.services import snapshot_refresh_service

    hb_task: asyncio.Task | None = None
    try:
        _mark_job_running(job_id)
        hb_task = asyncio.create_task(_heartbeat_loop(job_id))
        job_store.append_step(job_id, "snapshot_refresh")
        max_seconds = get_settings().snapshot_refresh_max_seconds

        def _progress(note: str) -> None:
            job_store.update_job(job_id, current_step="snapshot_refresh")
            # Append note onto the active step without finishing it
            job = job_store.get_job(job_id)
            if not job:
                return
            progress = list(job.get("progress") or [])
            for step in reversed(progress):
                if step.get("step") == "snapshot_refresh" and step.get("status") == "running":
                    step["note"] = note
                    break
            job_store.update_job(job_id, progress=progress)

        try:
            result = await asyncio.wait_for(
                snapshot_refresh_service.refresh_snapshots(
                    mode=mode,
                    end_month=end_month,
                    metric_keys=metric_keys,
                    progress_cb=_progress,
                ),
                timeout=max_seconds,
            )
        except asyncio.TimeoutError:
            logger.error("Snapshot refresh job %s timed out after %ss", job_id, max_seconds)
            _fail_job_on_timeout(job_id, max_seconds)
            return

        status = result.get("status") or "done"
        if status == "failed":
            job_store.finish_step(
                job_id,
                "snapshot_refresh",
                "failed",
                "; ".join(result.get("errors") or []) or "refresh failed",
            )
            job_store.update_job(
                job_id,
                status="failed",
                error="; ".join(result.get("errors") or []) or "snapshot refresh failed",
                result=result,
                current_step=None,
                finished_at=_utc_now(),
            )
            return

        note = (
            f"{result.get('metrics_refreshed', 0)} metrics · "
            f"{result.get('months_window')} · source={result.get('source')}"
        )
        job_store.finish_step(job_id, "snapshot_refresh", "done", note)
        job_store.update_job(
            job_id,
            status="done",
            result=result,
            current_step=None,
            finished_at=_utc_now(),
        )
        logger.info("Snapshot refresh job %s done run_id=%s", job_id, result.get("run_id"))
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
        logger.exception("Snapshot refresh job %s failed", job_id)
        _fail_job_on_error(job_id, e)
    finally:
        if hb_task is not None:
            hb_task.cancel()
            try:
                await hb_task
            except (asyncio.CancelledError, Exception):
                pass
