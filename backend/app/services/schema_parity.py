"""Fabric vs Postgres-mirror schema parity checks (Phase F).

The Postgres WH_Silver mirror must stay structurally identical to Fabric for
the auto-fallback to be safe. Nothing warns automatically when someone alters
one side, so this module re-implements the deep-audit parity check as a
repeatable tool: column names, row counts, Postgres NAMEDATALEN truncation
suspects (identifiers silently cut at 63 chars on CREATE TABLE), and data-type
differences (informational — the mirror intentionally casts a few money/rate
columns to numeric while Fabric reports varchar).

Pure comparison functions are separated from live fetching so they are fully
unit-testable offline. Live fetching is read-only on both sides (SELECT against
INFORMATION_SCHEMA / COUNT(*) only, through the same guarded connectors the
app uses). CLI entry point: scripts/verify_pg_parity.py.
"""

from __future__ import annotations

from typing import Any

# PostgreSQL NAMEDATALEN default: identifiers longer than 63 bytes are
# silently truncated at CREATE TABLE time (no error, no warning).
PG_NAMEDATALEN = 63

# Cross-dialect normalization so "varchar" (Fabric) == "character varying" (PG).
_TYPE_ALIASES = {
    "character varying": "varchar",
    "character": "char",
    "nchar": "char",
    "nvarchar": "varchar",
    "timestamp without time zone": "datetime",
    "timestamp with time zone": "datetime",
    "datetime2": "datetime",
    "double precision": "float",
    "real": "float",
    "decimal": "numeric",
    "money": "numeric",
    "int": "integer",
    "int4": "integer",
    "int8": "bigint",
    "bool": "boolean",
    "bit": "boolean",
}


def normalize_type(data_type: str) -> str:
    t = (data_type or "").strip().lower()
    return _TYPE_ALIASES.get(t, t)


def find_overlong_names(column_names: list[str]) -> list[str]:
    """Column names that exceed PG's NAMEDATALEN and would be silently truncated."""
    return [c for c in column_names if len(c.encode("utf-8")) > PG_NAMEDATALEN]


def compare_columns(
    fabric_columns: list[dict[str, Any]],
    pg_columns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare one table's columns. Each entry: {"column_name", "data_type"}.

    Returns a report with:
    - missing_in_pg / extra_in_pg: name-level drift (case-sensitive — both
      sides use the same business-friendly names)
    - truncation_suspects: Fabric name > 63 chars whose 63-char prefix exists
      on the PG side (the NAMEDATALEN silent-cut signature, Phase F issue #1)
    - type_diffs: same column, different normalized type (informational —
      expected for the intentionally numeric-cast mirror columns)
    """
    fabric_types = {c["column_name"]: str(c.get("data_type", "")) for c in fabric_columns}
    pg_types = {c["column_name"]: str(c.get("data_type", "")) for c in pg_columns}
    fabric_names = set(fabric_types)
    pg_names = set(pg_types)

    missing_in_pg = sorted(fabric_names - pg_names)
    extra_in_pg = sorted(pg_names - fabric_names)

    truncation_suspects: list[dict[str, str]] = []
    for name in list(missing_in_pg):
        if len(name) > PG_NAMEDATALEN:
            prefix = name[:PG_NAMEDATALEN]
            if prefix in pg_names:
                truncation_suspects.append({"fabric": name, "postgres": prefix})
                missing_in_pg.remove(name)
                if prefix in extra_in_pg:
                    extra_in_pg.remove(prefix)

    type_diffs: list[dict[str, str]] = []
    for name in sorted(fabric_names & pg_names):
        f_type = normalize_type(fabric_types[name])
        p_type = normalize_type(pg_types[name])
        if f_type != p_type:
            type_diffs.append(
                {"column": name, "fabric": fabric_types[name], "postgres": pg_types[name]}
            )

    return {
        "matched": len(fabric_names & pg_names),
        "missing_in_pg": missing_in_pg,
        "extra_in_pg": extra_in_pg,
        "truncation_suspects": truncation_suspects,
        "type_diffs": type_diffs,
        "overlong_fabric_names": find_overlong_names(sorted(fabric_names)),
    }


def build_parity_report(
    fabric_tables: dict[str, dict[str, Any]],
    pg_tables: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Full-schema parity report.

    Input shape per side: {table_name: {"columns": [...], "row_count": int|None}}.
    Table status:
    - "ok"            — columns and row counts match
    - "type_diff"     — only data types differ (informational)
    - "mismatch"      — column names differ / truncation suspect / row counts differ
    - "missing_in_pg" / "missing_in_fabric" — table exists on one side only
    Report "drift" is True when anything other than ok/type_diff exists.
    """
    tables: dict[str, dict[str, Any]] = {}
    all_names = sorted(set(fabric_tables) | set(pg_tables))
    for name in all_names:
        if name not in pg_tables:
            tables[name] = {"status": "missing_in_pg"}
            continue
        if name not in fabric_tables:
            tables[name] = {"status": "missing_in_fabric"}
            continue

        f_meta = fabric_tables[name]
        p_meta = pg_tables[name]
        col_report = compare_columns(f_meta.get("columns", []), p_meta.get("columns", []))

        f_count = f_meta.get("row_count")
        p_count = p_meta.get("row_count")
        row_count_match = None
        if f_count is not None and p_count is not None:
            row_count_match = int(f_count) == int(p_count)

        name_drift = bool(
            col_report["missing_in_pg"]
            or col_report["extra_in_pg"]
            or col_report["truncation_suspects"]
        )
        if name_drift or row_count_match is False:
            status = "mismatch"
        elif col_report["type_diffs"]:
            status = "type_diff"
        else:
            status = "ok"

        tables[name] = {
            "status": status,
            "columns": col_report,
            "row_count": {
                "fabric": f_count,
                "postgres": p_count,
                "match": row_count_match,
            },
        }

    drift_tables = [
        n for n, t in tables.items() if t["status"] not in ("ok", "type_diff")
    ]
    return {
        "tables": tables,
        "total": len(all_names),
        "ok": sum(1 for t in tables.values() if t["status"] == "ok"),
        "type_diff_only": sum(1 for t in tables.values() if t["status"] == "type_diff"),
        "drift_tables": drift_tables,
        "drift": bool(drift_tables),
    }


# ── Live fetching (read-only; used by scripts/verify_pg_parity.py) ──────────


def _quote_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def fetch_fabric_table_meta(
    schema: str, *, include_row_counts: bool = True
) -> dict[str, dict[str, Any]]:
    """Fetch {table: {columns, row_count}} from live Fabric (SELECT-only)."""
    from backend.app.services.fabric_connector import get_fabric_connector

    connector = get_fabric_connector()
    safe_schema = _quote_sql_literal(schema)
    result = connector.execute_read_only(
        "SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name, DATA_TYPE AS data_type "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = '{safe_schema}' "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION",
        mode="parity_check",
        max_rows=100000,
    )
    tables = _group_columns(result.get("rows", []))
    if include_row_counts:
        for name, meta in tables.items():
            meta["row_count"] = _fabric_row_count(connector, schema, name)
    return tables


def fetch_pg_table_meta(
    schema: str, *, include_row_counts: bool = True
) -> dict[str, dict[str, Any]]:
    """Fetch {table: {columns, row_count}} from the live Postgres mirror (SELECT-only)."""
    from backend.app.services.postgres_replica import get_postgres_connector

    connector = get_postgres_connector()
    safe_schema = _quote_sql_literal(schema)
    result = connector.execute_read_only(
        "SELECT table_name AS table_name, column_name AS column_name, data_type AS data_type "
        "FROM information_schema.columns "
        f"WHERE table_schema = '{safe_schema}' "
        "ORDER BY table_name, ordinal_position",
        mode="parity_check",
        max_rows=100000,
    )
    tables = _group_columns(result.get("rows", []))
    if include_row_counts:
        for name, meta in tables.items():
            meta["row_count"] = _pg_row_count(connector, schema, name)
    return tables


def _group_columns(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for row in rows:
        table = str(row.get("table_name", ""))
        if not table:
            continue
        meta = tables.setdefault(table, {"columns": [], "row_count": None})
        meta["columns"].append(
            {
                "column_name": str(row.get("column_name", "")),
                "data_type": str(row.get("data_type", "")),
            }
        )
    return tables


def _fabric_row_count(connector: Any, schema: str, table: str) -> int | None:
    try:
        result = connector.execute_read_only(
            f'SELECT COUNT(*) AS cnt FROM [{schema}].[{table}]',
            mode="parity_check",
            max_rows=1,
        )
        rows = result.get("rows") or []
        return int(rows[0]["cnt"]) if rows else None
    except Exception:
        return None


def _pg_row_count(connector: Any, schema: str, table: str) -> int | None:
    try:
        # Identifiers are double-quoted (mixed-case business names); embedded
        # quotes doubled per SQL rules.
        safe_schema = schema.replace('"', '""')
        safe_table = table.replace('"', '""')
        result = connector.execute_read_only(
            f'SELECT COUNT(*) AS cnt FROM "{safe_schema}"."{safe_table}"',
            mode="parity_check",
            max_rows=1,
        )
        rows = result.get("rows") or []
        return int(rows[0]["cnt"]) if rows else None
    except Exception:
        return None
