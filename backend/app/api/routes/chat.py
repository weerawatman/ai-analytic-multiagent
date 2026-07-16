from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from backend.app.agents.orchestrator import graph
from backend.app.agents.state import AgentState
from backend.app.core.logger import logger
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.backlog import BacklogItemResponse
from backend.app.services import chat_store
from backend.app.services.chat_lock import thread_lock
from backend.app.services.quality_assembly import save_quality_to_backlog

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI Data Team."""
    lock = thread_lock(request.thread_id)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Thread is still processing a previous question — wait for it to finish",
        )

    async with lock:
        return await _run_chat(request)


async def _run_chat(request: ChatRequest) -> ChatResponse:
    logger.info(
        "Chat request: thread=%s mode=%s message=%s...",
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

    try:
        result = await graph.ainvoke(input_state.model_dump(), config=config)
    except Exception as e:
        logger.error("Graph execution failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    state = AgentState(**result)

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
        )

    answer = state.final_answer or state.query_result or state.ba_summary or ""
    if not answer.strip():
        answer = (
            "[ไม่มีข้อความตอบจาก agent — ลองใช้ Explore mode และเลือก theme ที่มี CE1SATG ก่อนถามใหม่]"
        )
    quality_payload = state.quality_payload or None
    quality_gaps = quality_payload.get("quality_gaps") if quality_payload else None

    agents_involved = (
        quality_payload.get("agents_involved", []) if quality_payload else []
    )
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
        quality_payload=quality_payload if quality_payload else None,
        quality_gaps=quality_gaps,
    )


@router.post("/save-candidate", response_model=BacklogItemResponse)
async def save_candidate(payload: dict) -> BacklogItemResponse:
    """Save quality payload to insight backlog (Quality Bar D)."""
    try:
        item = save_quality_to_backlog(payload)
        return BacklogItemResponse(**item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
