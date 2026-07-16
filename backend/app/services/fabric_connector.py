"""Microsoft Fabric Data Warehouse connector (Service Principal, read-only)."""

from __future__ import annotations

import struct
from contextlib import contextmanager
from typing import Any, Generator

import pyodbc
from azure.identity import ClientSecretCredential

from backend.app.core.config import Settings, get_settings
from backend.app.core.logger import logger
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql

SQL_COPT_SS_ACCESS_TOKEN = 1256
TOKEN_SCOPE = "https://database.windows.net/.default"


class FabricConnectionError(RuntimeError):
    """Raised when Fabric connection or query fails."""

    def __init__(self, message: str, message_th: str | None = None) -> None:
        super().__init__(message)
        self.message_th = message_th or message


class FabricConnector:
    """Connect to Fabric DW using Entra ID Service Principal."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_configured(self) -> bool:
        return self.settings.fabric_is_configured

    def _access_token(self) -> str:
        credential = ClientSecretCredential(
            tenant_id=self.settings.fabric_tenant_id,
            client_id=self.settings.fabric_client_id,
            client_secret=self.settings.fabric_client_secret,
        )
        return credential.get_token(TOKEN_SCOPE).token

    def _connection_string(self) -> str:
        return (
            f"Driver={{{self.settings.fabric_odbc_driver}}};"
            f"Server=tcp:{self.settings.fabric_server},1433;"
            f"Database={self.settings.fabric_database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
            f"Connection Timeout={self.settings.fabric_connection_timeout};"
        )

    def _token_struct(self, token: str) -> bytes:
        token_bytes = token.encode("utf-16-le")
        return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    @contextmanager
    def connect(self) -> Generator[pyodbc.Connection, None, None]:
        if not self.is_configured():
            raise FabricConnectionError(
                "Fabric credentials are not configured in .env",
                "ยังไม่ได้ตั้งค่า Fabric ใน .env",
            )

        token = self._access_token()
        conn = pyodbc.connect(
            self._connection_string(),
            attrs_before={SQL_COPT_SS_ACCESS_TOKEN: self._token_struct(token)},
        )
        # Query timeout (SQL_ATTR_QUERY_TIMEOUT) — login timeout is set in the
        # connection string; without this a heavy query can run unbounded.
        conn.timeout = self.settings.fabric_query_timeout
        try:
            yield conn
        finally:
            conn.close()

    def ping(self) -> dict[str, Any]:
        """Test connectivity with SELECT 1."""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()
            return {
                "connected": True,
                "database": self.settings.fabric_database,
                "server": self.settings.fabric_server,
                "result": row[0] if row else None,
            }

    def execute_read_only(
        self,
        sql: str,
        *,
        mode: str = "explore",
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Validate and execute a read-only query."""
        limit = max_rows or self.settings.fabric_max_rows
        try:
            safe_sql = validate_read_only_sql(sql)
        except SQLGuardError as exc:
            logger.warning("SQL guard rejected query [%s]: %s", mode, exc)
            raise

        logger.info("Executing Fabric query [%s]: %s...", mode, safe_sql[:120])

        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(safe_sql)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(limit)
            data = [dict(zip(columns, row)) for row in rows]

        return {
            "sql": safe_sql,
            "columns": columns,
            "rows": data,
            "row_count": len(data),
            "truncated": len(data) >= limit,
            "mode": mode,
        }

    def fetch_schema_summary(self, top_schemas: int = 20) -> list[dict[str, Any]]:
        """Fetch table metadata for theme discovery."""
        sql = f"""
        SELECT TOP ({top_schemas * 50})
            TABLE_SCHEMA AS table_schema,
            TABLE_NAME AS table_name,
            TABLE_TYPE AS table_type
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        result = self.execute_read_only(sql, mode="schema_scan", max_rows=top_schemas * 50)
        return result["rows"]


_fabric_connector: FabricConnector | None = None


def get_fabric_connector() -> FabricConnector:
    global _fabric_connector
    if _fabric_connector is None:
        _fabric_connector = FabricConnector()
    return _fabric_connector
