from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from backend.app.agents.orchestrator import graph
from backend.app.agents.state import AgentState
from backend.app.core.logger import logger
from backend.app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI Data Team."""
    logger.info("Chat request: thread=%s message=%s...", request.thread_id, request.message[:80])

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
        return ChatResponse(
            thread_id=request.thread_id,
            agent=state.current_agent,
            content=state.schema_info,
            requires_approval=True,
            pending_action="semantic_layer_update",
        )

    return ChatResponse(
        thread_id=request.thread_id,
        agent=state.current_agent,
        content=state.final_answer or "No response generated.",
        requires_approval=False,
    )
