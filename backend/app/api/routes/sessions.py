from fastapi import APIRouter, HTTPException

from backend.app.schemas.backlog import MessageResponse, SessionSummary
from backend.app.services import chat_store

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    sessions = chat_store.list_sessions()
    return [SessionSummary(**s) for s in sessions]


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session_id: str) -> list[MessageResponse]:
    messages = chat_store.get_messages(session_id)
    if not messages:
        # Distinguish missing session vs empty — check sessions table
        sessions = chat_store.list_sessions(limit=1000)
        if not any(s["id"] == session_id for s in sessions):
            raise HTTPException(status_code=404, detail="Session not found")
    return [MessageResponse(**m) for m in messages]
