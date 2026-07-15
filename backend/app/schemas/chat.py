from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    thread_id: str = Field(..., description="Unique conversation thread identifier")
    message: str = Field(..., min_length=1, description="User message")
    mode: Literal["explore", "trusted"] = "explore"
    theme: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    agent: str = Field(..., description="Agent that produced the response")
    content: str
    requires_approval: bool = False
    pending_action: str | None = None
