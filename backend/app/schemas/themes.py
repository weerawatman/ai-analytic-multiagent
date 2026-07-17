from pydantic import BaseModel, Field


class ThemeItem(BaseModel):
    id: str
    name_th: str
    rationale_th: str
    table_count: int = 0
    sample_tables: list[str] = Field(default_factory=list)
    starter_questions_th: list[str] = Field(default_factory=list)


class ThemeScanResponse(BaseModel):
    scanned_at: str | None = None
    database: str | None = None
    total_tables_scanned: int | None = None
    themes: list[ThemeItem] = Field(default_factory=list)
    message: str | None = None
    # Which live source produced the scan: 'fabric' | 'postgres' | 'cache'
    source: str | None = None
