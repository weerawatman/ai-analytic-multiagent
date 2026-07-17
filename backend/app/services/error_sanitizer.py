"""Sanitize step_errors before they reach any CEO-visible or external surface.

Full technical detail (ODBC text, exception args, tracebacks) stays in
backend.log and in the raw ``step_errors`` state for debugging. These helpers
produce the short polite Thai form (step label + exception type only) used for
job progress notes, the BA prompt warnings, and consultant (Claude) payloads.
"""

from __future__ import annotations

import re

# Step labels agents prepend, e.g. "data_analyst SQL: ..." / "business_analyst: ...".
_STEP_PREFIX_RE = re.compile(r"^([A-Za-z_]+(?:\s+SQL)?):\s+")
_EXC_TYPE_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Error|Exception)\b")
_THAI_RE = re.compile(r"[\u0e00-\u0e7f]")
_TECH_DETAIL_RE = re.compile(
    r"ODBC|SQLSTATE|\[Microsoft\]|pyodbc|Traceback|HYT00|42S22|42000"
    r"|psycopg2|42703|57014|08006",
    re.IGNORECASE,
)

SANITIZED_NOTE_TH = "ขั้นตอนนี้ทำงานไม่สำเร็จ"


def sanitize_error_entry(raw: object) -> str:
    """Short, polite version of one step_errors entry.

    Keeps the step label (``data_analyst SQL``) and the exception type name,
    drops everything else. Entries that are already clean Thai summaries
    (e.g. the RowCountExceeded guidance) pass through unchanged so the reader
    still gets actionable advice.
    """
    text = " ".join(str(raw).split())
    prefix = ""
    match = _STEP_PREFIX_RE.match(text)
    if match:
        prefix = f"{match.group(1)}: "
        text = text[match.end():]

    exc = _EXC_TYPE_RE.search(text)
    if exc:
        # Clean when only closing punctuation follows the type name,
        # e.g. "ชื่อคอลัมน์ใน SQL ไม่ถูกต้อง (ProgrammingError)".
        tail = text[exc.end():].strip(" '\")]}.,;—–-")
        if not tail and not _TECH_DETAIL_RE.search(text):
            return prefix + text
        return f"{prefix}{SANITIZED_NOTE_TH} ({exc.group()})"
    if _THAI_RE.search(text) and not _TECH_DETAIL_RE.search(text):
        return prefix + text
    return f"{prefix}{SANITIZED_NOTE_TH}"


def sanitize_step_errors(errors: list | None) -> list[str]:
    """Sanitized copy of a step_errors list (originals stay untouched)."""
    return [sanitize_error_entry(e) for e in (errors or [])]
