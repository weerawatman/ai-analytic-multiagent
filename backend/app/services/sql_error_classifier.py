"""Pure SQL-error classification — shared by data_analyst.py and lesson_miner.py.

Extracted from data_analyst.py (Phase J) so a services/ module (lesson_miner)
does not need to import from app.agents (inverted layering).
"""

from __future__ import annotations

from backend.app.services.fabric_sql import RowCountExceeded


def classify_sql_error(error: BaseException | str) -> str:
    """Map an exception (or prior friendly summary) to a retry/PDCA class.

    Classes stay coarse on purpose: enough signal for guidance without
    embedding raw ODBC text into state.sql_error / quality_payload.
    """
    text = str(error)
    lower = text.lower()
    if isinstance(error, RowCountExceeded) or "เกินเกณฑ์" in text or "exceeds threshold" in lower:
        return "row_count"
    if (
        "Invalid column name" in text
        or "42S22" in text
        or "ชื่อคอลัมน์" in text
        or "42703" in text  # Postgres undefined_column SQLSTATE
        or ("column" in lower and "does not exist" in lower)  # psycopg2 UndefinedColumn text
    ):
        return "invalid_column"
    if (
        "timeout" in lower
        or "timed out" in lower
        or "HYT00" in text
        or "เกินเวลา" in text
        or "57014" in text  # Postgres query_canceled (statement_timeout)
    ):
        return "timeout"
    if (
        "connection" in lower
        or "login failed" in lower
        or "could not connect" in lower  # psycopg2 OperationalError
        or "08006" in text  # Postgres connection_failure SQLSTATE
        or "08001" in text
        or "08S01" in text
        or "เชื่อมต่อ" in text
    ):
        return "connection"
    return "generic"


__all__ = ["classify_sql_error"]
