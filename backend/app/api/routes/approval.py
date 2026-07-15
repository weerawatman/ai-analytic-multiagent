from fastapi import APIRouter, HTTPException
from langgraph.checkpoint.memory import MemorySaver

from backend.app.agents.orchestrator import graph
from backend.app.agents.state import AgentState
from backend.app.core.logger import logger
from backend.app.schemas.approval import ApprovalRequest, ApprovalResponse
from backend.app.services.semantic_store import write_semantic_layer

router = APIRouter(prefix="/approval", tags=["Approval"])


@router.post("/", response_model=ApprovalResponse)
async def handle_approval(request: ApprovalRequest) -> ApprovalResponse:
    """Handle human-in-the-loop approval for semantic layer updates."""
    logger.info(
        "Approval request: thread=%s approved=%s", request.thread_id, request.approved
    )

    config = {"configurable": {"thread_id": request.thread_id}}

    # Get the current graph state
    current_state = await graph.aget_state(config)
    if current_state is None or current_state.values is None:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval found for thread {request.thread_id}",
        )

    state_values = current_state.values
    approval_status = "approved" if request.approved else "rejected"

    # If approved, persist the semantic layer
    if request.approved and state_values.get("semantic_layer"):
        try:
            await write_semantic_layer(state_values["semantic_layer"])
            logger.info("Semantic layer persisted for thread=%s", request.thread_id)
        except Exception as e:
            logger.error("Failed to persist semantic layer: %s", e)
            raise HTTPException(status_code=500, detail="Failed to save semantic layer")

    # Resume the graph with updated approval status
    update = {"approval_status": approval_status}
    if request.feedback:
        from langchain_core.messages import HumanMessage
        update["messages"] = [HumanMessage(content=f"User feedback: {request.feedback}")]

    try:
        result = await graph.ainvoke(
            update,
            config=config,
        )
    except Exception as e:
        logger.error("Graph resume failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Resume error: {e}")

    result_state = AgentState(**result)

    return ApprovalResponse(
        thread_id=request.thread_id,
        status=approval_status,
        agent=result_state.current_agent,
        content=result_state.final_answer or "Process completed.",
    )
