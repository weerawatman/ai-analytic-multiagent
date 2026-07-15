from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    thread_id: str = Field(..., description="Thread to resume")
    approved: bool = Field(..., description="Whether the user approves the action")
    feedback: str | None = Field(None, description="Optional user feedback")


class ApprovalResponse(BaseModel):
    thread_id: str
    status: str
    agent: str
    content: str
