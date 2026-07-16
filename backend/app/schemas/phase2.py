from pydantic import BaseModel, Field


class DiscoveryRunResponse(BaseModel):
    theme_id: str
    discovered_at: str
    database: str
    tables_profiled: int
    profiles: list[dict]
    relationships: list[dict]


class KnowledgeItemCreate(BaseModel):
    theme: str | None = None
    field_key: str | None = None
    table_name: str | None = None
    definition_th: str | None = None
    name_th: str | None = None
    description_th: str | None = None
    from_table: str | None = None
    to_table: str | None = None
    join_keys: str | None = None
    status: str = "draft"


class KnowledgeItemResponse(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str


class BriefingResponse(BaseModel):
    theme_id: str
    theme_name: str | None = None
    generated_at: str
    briefs: list[dict]


class FeedbackCreate(BaseModel):
    brief_id: str
    role: str
    action: str
    comment: str = ""


class FeedbackResponse(BaseModel):
    theme_id: str
    entries: list[dict]
