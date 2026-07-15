"""Read-only SQL validation before Fabric execution."""

import re

BLOCKED_PATTERN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|"
    r"EXEC|EXECUTE|GRANT|REVOKE|DENY|BACKUP|RESTORE|"
    r"xp_|sp_|OPENROWSET|BULK|INTO\s+"
    r")\b",
    re.IGNORECASE,
)

ALLOWED_START = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE | re.DOTALL)


class SQLGuardError(ValueError):
    """Raised when SQL fails read-only validation."""

    def __init__(self, message: str, message_th: str | None = None) -> None:
        super().__init__(message)
        self.message_th = message_th or message


def _strip_comments(sql: str) -> str:
    """Remove line and block comments for safer parsing."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql.strip()


def validate_read_only_sql(sql: str) -> str:
    """
    Validate SQL is read-only (SELECT / WITH only).
    Returns normalized SQL on success.
    Raises SQLGuardError on violation.
    """
    if not sql or not sql.strip():
        raise SQLGuardError(
            "SQL query is empty.",
            "คำสั่ง SQL ว่างเปล่า",
        )

    normalized = _strip_comments(sql)
    if ";" in normalized.rstrip(";"):
        raise SQLGuardError(
            "Multiple SQL statements are not allowed.",
            "ไม่อนุญาตให้รันหลายคำสั่ง SQL ในครั้งเดียว",
        )

    if not ALLOWED_START.match(normalized):
        raise SQLGuardError(
            "Only SELECT or WITH (CTE) queries are allowed.",
            "อนุญาตเฉพาะคำสั่ง SELECT หรือ WITH (CTE) เท่านั้น",
        )

    if BLOCKED_PATTERN.search(normalized):
        raise SQLGuardError(
            "Query contains blocked write or admin keywords.",
            "คำสั่งมีคีย์เวิร์ดที่ไม่อนุญาต (เขียนข้อมูล/แก้ไข schema)",
        )

    return normalized.rstrip(";").strip()
