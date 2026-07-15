from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from backend.app.agents.orchestrator import graph
from backend.app.agents.state import AgentState
from backend.app.core.logger import logger
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services import chat_store

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI Data Team."""
    logger.info("Chat request: thread=%s message=%s...", request.thread_id, request.message[:80])

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

    answer = state.final_answer or "No response generated."
    chat_store.add_message(
        request.thread_id,
        role="assistant",
        content=answer,
        agent=state.current_agent,
        mode=request.mode,
        theme=request.theme,
    )

    return ChatResponse(
        thread_id=request.thread_id,
        agent=state.current_agent,
        content=answer,
        requires_approval=False,
    )
