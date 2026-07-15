from typing import Any, Literal

from pydantic import BaseModel, Field


class BacklogCreateRequest(BaseModel):
    theme: str = ""
    mode: Literal["explore", "trusted"] = "explore"
    question_th: str
    answer_summary_th: str = ""
    sql_primary: str = ""
    sql_alternative: str = ""
    assumptions: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    unknowns: list[str] = Field(default_factory=list)
    questions_for_ba_da: list[str] = Field(default_factory=list)
    sample_data_ref: str = ""
    status: Literal["new", "discussing", "validated", "rejected", "promoted"] = "new"


class BacklogUpdateRequest(BaseModel):
    theme: str | None = None
    mode: Literal["explore", "trusted"] | None = None
    question_th: str | None = None
    answer_summary_th: str | None = None
    sql_primary: str | None = None
    sql_alternative: str | None = None
    assumptions: list[str] | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    unknowns: list[str] | None = None
    questions_for_ba_da: list[str] | None = None
    sample_data_ref: str | None = None
    status: Literal["new", "discussing", "validated", "rejected", "promoted"] | None = None
    feedback: str | None = None


class BacklogItemResponse(BaseModel):
    id: str
    theme: str
    mode: str
    question_th: str
    answer_summary_th: str
    sql_primary: str
    sql_alternative: str
    assumptions: list[str]
    confidence: str
    unknowns: list[str]
    questions_for_ba_da: list[str]
    sample_data_ref: str
    status: str
    ba_da_feedback: list[dict[str, Any]]
    created_at: str
    updated_at: str


class SessionSummary(BaseModel):
    id: str
    title: str | None
    mode: str
    theme: str | None
    created_at: str
    updated_at: str
    message_count: int = 0


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    agent: str | None
    content: str
    created_at: str
