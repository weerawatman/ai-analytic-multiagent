from typing import Any

from pydantic import BaseModel, Field


class JobSubmitResponse(BaseModel):
    job_id: str
    thread_id: str | None = None
    status: str = "queued"
    kind: str = "chat"


class JobStepInfo(BaseModel):
    step: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    note: str | None = None


class JobStatusResponse(BaseModel):
    id: str
    kind: str
    thread_id: str | None = None
    status: str
    question: str | None = None
    current_step: str | None = None
    progress: list[JobStepInfo] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
