"""SAP table descriptions (DD02T export) — SQLite lookup for agent context."""

from __future__ import annotations

import csv
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from backend.app.core.logger import logger
from backend.app.services.local_paths import get_local_dir

DB_NAME = "sap_tables.db"
DEFAULT_LANGUAGE = "E"
BATCH_SIZE = 5000

_SUFFIX_PATTERNS = (
    re.compile(r"_ALL_CLEANED$", re.I),
    re.compile(r"_CLEANED$", re.I),
    re.compile(r"_ALL$", re.I),
)


def _db_path() -> Path:
    path = get_local_dir() / "knowledge" / DB_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sap_table_descriptions (
                tabname TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'E',
                description TEXT NOT NULL,
                PRIMARY KEY (tabname, language)
            );
            CREATE INDEX IF NOT EXISTS idx_sap_tabname ON sap_table_descriptions(tabname);

            CREATE TABLE IF NOT EXISTS sap_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tabname_candidates(table_ref: str) -> list[str]:
    """Map Fabric table ref to possible SAP TABNAME keys."""
    raw = table_ref.split(".")[-1].strip().upper()
    if not raw:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        n = name.strip().upper()
        if n and n not in seen:
            seen.add(n)
            candidates.append(n)

    add(raw)
    if raw.startswith("DIM_"):
        add(raw[4:])
    if raw.startswith("/"):
        add(raw.lstrip("/"))

    stripped = raw
    for pattern in _SUFFIX_PATTERNS:
        stripped = pattern.sub("", stripped)
    if stripped != raw:
        add(stripped)
    if stripped.startswith("DIM_"):
        add(stripped[4:])

    return candidates


def import_from_csv(
    csv_path: str | Path,
    *,
    language: str = DEFAULT_LANGUAGE,
    replace: bool = True,
) -> dict[str, Any]:
    """Import SAP DD02T-style CSV: TABNAME, DDLANGUAGE, DDTEXT."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    init_db()
    imported = 0
    skipped = 0

    with _connection() as conn:
        if replace:
            conn.execute(
                "DELETE FROM sap_table_descriptions WHERE language = ?",
                (language.upper(),),
            )

        batch: list[tuple[str, str, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise ValueError("CSV has no header row")

            fields = {f.upper(): f for f in reader.fieldnames}
            tab_col = fields.get("TABNAME")
            lang_col = fields.get("DDLANGUAGE")
            text_col = fields.get("DDTEXT")
            if not all([tab_col, lang_col, text_col]):
                raise ValueError(
                    "CSV must have columns TABNAME, DDLANGUAGE, DDTEXT "
                    f"(found: {reader.fieldnames})"
                )

            for row in reader:
                row_lang = str(row.get(lang_col, "")).strip().upper()
                if row_lang != language.upper():
                    skipped += 1
                    continue
                tabname = str(row.get(tab_col, "")).strip().upper()
                description = str(row.get(text_col, "")).strip()
                if not tabname or not description:
                    skipped += 1
                    continue
                batch.append((tabname, row_lang, description))
                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        "INSERT OR REPLACE INTO sap_table_descriptions "
                        "(tabname, language, description) VALUES (?, ?, ?)",
                        batch,
                    )
                    imported += len(batch)
                    batch.clear()

            if batch:
                conn.executemany(
                    "INSERT OR REPLACE INTO sap_table_descriptions "
                    "(tabname, language, description) VALUES (?, ?, ?)",
                    batch,
                )
                imported += len(batch)

        conn.execute(
            "INSERT OR REPLACE INTO sap_metadata (key, value) VALUES (?, ?)",
            ("imported_at", _utc_now()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO sap_metadata (key, value) VALUES (?, ?)",
            ("source_file", str(path.resolve())),
        )
        conn.execute(
            "INSERT OR REPLACE INTO sap_metadata (key, value) VALUES (?, ?)",
            ("language", language.upper()),
        )

    logger.info("SAP table import done: %d rows (%d skipped)", imported, skipped)
    return {
        "imported": imported,
        "skipped": skipped,
        "language": language.upper(),
        "source_file": str(path.resolve()),
        "imported_at": _utc_now(),
    }


def get_stats() -> dict[str, Any]:
    init_db()
    with _connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sap_table_descriptions"
        ).fetchone()["cnt"]
        meta = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM sap_metadata")
        }
    return {
        "table_count": count,
        "imported_at": meta.get("imported_at"),
        "source_file": meta.get("source_file"),
        "language": meta.get("language", DEFAULT_LANGUAGE),
        "db_path": str(_db_path()),
    }


def lookup_description(
    tabname: str,
    *,
    language: str = DEFAULT_LANGUAGE,
) -> str | None:
    init_db()
    name = tabname.strip().upper()
    with _connection() as conn:
        row = conn.execute(
            "SELECT description FROM sap_table_descriptions "
            "WHERE tabname = ? AND language = ?",
            (name, language.upper()),
        ).fetchone()
    return row["description"] if row else None


def lookup_for_table_ref(
    table_ref: str,
    *,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, str] | None:
    """Return matched SAP tabname and description for a Fabric table ref."""
    for candidate in tabname_candidates(table_ref):
        desc = lookup_description(candidate, language=language)
        if desc:
            return {"sap_tabname": candidate, "description": desc, "fabric_ref": table_ref}
    return None


def lookup_many(
    table_refs: list[str],
    *,
    language: str = DEFAULT_LANGUAGE,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    for ref in table_refs:
        key = ref.lower()
        if key in seen_refs:
            continue
        seen_refs.add(key)
        match = lookup_for_table_ref(ref, language=language)
        if match:
            results.append(match)
    return results


def format_sap_tables_context(
    table_refs: list[str],
    *,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Format SAP descriptions for agent prompts."""
    matches = lookup_many(table_refs, language=language)
    if not matches:
        stats = get_stats()
        if stats["table_count"] == 0:
            return "(SAP table descriptions not imported — run import-sap-table-descriptions.ps1)"
        return "(no SAP descriptions matched for theme tables)"

    lines = ["## SAP Table Descriptions (DD02T)"]
    for m in matches:
        lines.append(f"- {m['fabric_ref']} → {m['sap_tabname']}: {m['description']}")
    return "\n".join(lines)
