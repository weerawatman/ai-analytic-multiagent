from pydantic import BaseModel, Field


class TrustedMetricPreview(BaseModel):
    metric_key: str
    display_name_th: str
    business_definition_th: str
    sql_template: str
    grain: str
    standard_filters: list[str] = Field(default_factory=list)
    validated_assumptions: list[str] = Field(default_factory=list)
    playbook_th: str
    example_questions_th: list[str] = Field(default_factory=list)
    theme: str | None = None
    source_backlog_id: str


class PromotionPreviewResponse(BaseModel):
    item_id: str
    backlog_status: str
    metric: TrustedMetricPreview
    preview_markdown: str


class PromotionApproveRequest(BaseModel):
    approved: bool = True
    metric_key: str | None = None
    display_name_th: str | None = None
    business_definition_th: str | None = None
    playbook_th: str | None = None
    example_questions_th: list[str] | None = None
    approved_by: str = "data_engineer"


class PromotionApproveResponse(BaseModel):
    item_id: str
    status: str
    metric: TrustedMetricPreview | None = None
