"""Redact row-level data before any payload leaves the machine for Claude."""

from __future__ import annotations

import re
from typing import Any

from backend.app.core.config import get_settings
from backend.app.services.error_sanitizer import sanitize_step_errors

_ROW_BLOCK_RE = re.compile(
    r"^(QUERY_RESULT|SQL_RESULT|SQL_RETRY):\s*\n?\[[\s\S]*?\]\s*$",
    re.MULTILINE,
)
_SAMPLE_SECTION_RE = re.compile(
    r"###\s*ตัวอย่างข้อมูล\s*\n```json[\s\S]*?```",
    re.MULTILINE,
)

_REDACTION_MARK = "[ข้อมูลระดับแถวถูกตัดออก — ไม่ส่งออกภายนอก]"


def redact_for_external(text: str) -> str:
    if not text:
        return ""
    out = _ROW_BLOCK_RE.sub(_REDACTION_MARK, text)
    out = _SAMPLE_SECTION_RE.sub(_REDACTION_MARK, out)
    return out


def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n…[truncated]"


def build_consultant_sections(
    *,
    theme_id: str = "",
    theme: str = "",
    question: str = "",
    draft_answer: str = "",
    ba_summary: str = "",
    ds_critique: str = "",
    quality_payload: dict[str, Any] | None = None,
    step_errors: list[str] | None = None,
    include_troubleshooting: bool = False,
) -> dict[str, str]:
    """Whitelist-only sections safe to send externally.

    Never include sample_preview, sample_rows, or raw query_result.
    """
    from backend.app.services.discovery_service import format_schema_context_pack
    from backend.app.services.knowledge_store import format_knowledge_context
    from backend.app.services.team_memory_store import format_team_memory_context

    settings = get_settings()
    max_chars = settings.consultant_max_section_chars
    qp = quality_payload or {}

    def _safe_schema() -> str:
        try:
            # Prefer disk discovery; avoid live Fabric when theme_id missing
            if theme_id:
                return format_schema_context_pack(theme_id)
            return "(no theme_id — schema omitted for external consult)"
        except Exception as exc:
            return f"(schema unavailable: {type(exc).__name__})"

    def _safe_knowledge() -> str:
        try:
            return format_knowledge_context(theme=theme or theme_id or None)
        except Exception as exc:
            return f"(knowledge unavailable: {type(exc).__name__})"

    def _safe_team_memory() -> str:
        try:
            return format_team_memory_context(theme_id or None)
        except Exception as exc:
            return f"(team_memory unavailable: {type(exc).__name__})"

    sections: dict[str, str] = {
        "schema": _safe_schema(),
        "knowledge": _safe_knowledge(),
        "team_memory": _safe_team_memory(),
        "question": question,
        "draft_answer": draft_answer,
        "ba_summary": ba_summary or str(qp.get("ba_summary") or ""),
        "ds_critique": ds_critique or str(qp.get("ds_critique") or ""),
        "sql_primary": str(qp.get("sql_primary") or qp.get("sql") or ""),
        "sql_alternative": str(qp.get("sql_alternative") or ""),
        "assumptions": str(qp.get("assumptions") or ""),
        "confidence": str(qp.get("confidence") or ""),
        "unknowns": str(qp.get("unknowns") or ""),
        "quality_gaps": ", ".join(qp.get("quality_gaps") or [])
        if isinstance(qp.get("quality_gaps"), list)
        else str(qp.get("quality_gaps") or ""),
        # Sanitized (exception type + short Thai note) so Claude can never
        # echo ODBC/exception detail back into a CEO-visible reply.
        "step_errors": "; ".join(sanitize_step_errors(step_errors)),
    }

    if include_troubleshooting:
        gaps = sections["quality_gaps"]
        errs = sections["step_errors"]
        sections["troubleshooting"] = (
            f"ทีมติดขัด — quality_gaps: {gaps or '(none)'}; "
            f"step_errors: {errs or '(none)'}. "
            "ช่วยวินิจฉัยสาเหตุและเสนอวิธีแก้ที่ actionable ให้แต่ละตำแหน่ง (DE/DA/DS/BA)"
        )

    return {
        k: _cap(redact_for_external(v), max_chars)
        for k, v in sections.items()
        if v and str(v).strip()
    }


def sections_to_payload_text(sections: dict[str, str]) -> str:
    parts: list[str] = []
    for key, value in sections.items():
        parts.append(f"## {key}\n{value}")
    return "\n\n".join(parts)
