import asyncio

from backend.app.agents.state import AgentState
from backend.app.core.logger import logger
from backend.app.services.quality_assembly import (
    build_quality_payload,
    format_explore_response_th,
    validate_quality_bar_d,
)


async def quality_assembly_node(state: AgentState) -> dict:
    """Assemble Explore output to Quality Bar D format."""
    logger.info("Quality assembly for thread=%s mode=%s", state.thread_id, state.mode)

    # build_quality_payload re-executes SQL via pyodbc — keep it off the event loop.
    payload = await asyncio.to_thread(build_quality_payload, state)
    missing = validate_quality_bar_d(payload)
    if missing:
        logger.warning("Quality Bar D gaps: %s", missing)
        payload["quality_gaps"] = missing

    formatted = format_explore_response_th(payload)
    return {
        "quality_payload": payload,
        "final_answer": formatted,
        "query_result": formatted,
    }
