from pydantic import BaseModel


class ValidationCheck(BaseModel):
    id: str
    title: str
    passed: bool
    automated: bool
    detail: str
    manual_note: str | None = None


class ValidationSummary(BaseModel):
    passed: int
    total: int
    automated_passed: int
    automated_total: int
    ready_for_signoff: bool


class Phase1ValidationResponse(BaseModel):
    phase: str
    summary: ValidationSummary
    checks: list[ValidationCheck]
    sign_off_doc: str
