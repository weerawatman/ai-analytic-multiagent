"""PostgreSQL WH_Silver mirror connector — auto-fallback when Fabric is down.

Mirrors FabricConnector's shape (is_configured/connect/ping/execute_read_only)
so fabric_sql.py can dispatch to either connector transparently. Same
read-only enforcement (sql_guard) applies to both sources.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import psycopg2

from backend.app.core.config import Settings, get_settings
from backend.app.core.logger import logger
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql


class PostgresReplicaConnectionError(RuntimeError):
    """Raised when the Postgres replica connection or query fails."""

    def __init__(self, message: str, message_th: str | None = None) -> None:
        super().__init__(message)
        self.message_th = message_th or message


class PostgresReplicaConnector:
    """Connect to the Postgres WH_Silver mirror (read-only fallback for Fabric)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_configured(self) -> bool:
        return self.settings.pg_replica_is_configured

    @contextmanager
    def connect(self) -> Generator[Any, None, None]:
        if not self.is_configured():
            raise PostgresReplicaConnectionError(
                "Postgres replica credentials are not configured in .env",
                "ยังไม่ได้ตั้งค่า Postgres replica ใน .env",
            )
        conn = psycopg2.connect(
            host=self.settings.pg_replica_host,
            port=self.settings.pg_replica_port,
            dbname=self.settings.pg_replica_db,
            user=self.settings.pg_replica_user,
            password=self.settings.pg_replica_password,
            connect_timeout=self.settings.pg_replica_connect_timeout,
        )
        conn.set_session(readonly=True, autocommit=True)
        try:
            with conn.cursor() as cur:
                # ms — enforce per-query cap the same way fabric_query_timeout does.
                cur.execute("SET statement_timeout = %s", (self.settings.pg_replica_query_timeout * 1000,))
            yield conn
        finally:
            conn.close()

    def ping(self) -> dict[str, Any]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()
            return {
                "connected": True,
                "database": self.settings.pg_replica_db,
                "server": self.settings.pg_replica_host,
                "result": row[0] if row else None,
            }

    def execute_read_only(
        self,
        sql: str,
        *,
        mode: str = "explore",
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Validate and execute a read-only query against the Postgres replica."""
        limit = max_rows or self.settings.fabric_max_rows
        try:
            safe_sql = validate_read_only_sql(sql)
        except SQLGuardError as exc:
            logger.warning("SQL guard rejected query [pg %s]: %s", mode, exc)
            raise

        logger.info("Executing Postgres replica query [%s]: %s...", mode, safe_sql[:120])

        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(safe_sql)
            columns = [col.name for col in cursor.description] if cursor.description else []
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
        """Fetch table metadata for theme discovery (Postgres dialect: LIMIT, not TOP)."""
        sql = f"""
        SELECT
            table_schema AS table_schema,
            table_name AS table_name,
            table_type AS table_type
        FROM information_schema.tables
        WHERE table_type IN ('BASE TABLE', 'VIEW')
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        LIMIT {top_schemas * 50}
        """
        result = self.execute_read_only(sql, mode="schema_scan", max_rows=top_schemas * 50)
        return result["rows"]


_postgres_connector: PostgresReplicaConnector | None = None


def get_postgres_connector() -> PostgresReplicaConnector:
    global _postgres_connector
    if _postgres_connector is None:
        _postgres_connector = PostgresReplicaConnector()
    return _postgres_connector
