"""Resolve local data directory paths and ensure structure exists."""

import json
from pathlib import Path

from backend.app.core.config import Settings, get_settings


def get_project_root() -> Path:
    """Repository root (parent of backend/)."""
    return Path(__file__).resolve().parents[3]


def get_local_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = get_project_root() / settings.data_local_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_templates_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = get_project_root() / settings.data_templates_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_local_data_dir(settings: Settings | None = None) -> Path:
    """Scratch area for query exports / Phase E parquet & job-scoped models."""
    path = get_local_dir(settings) / "local_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_approved_models_dir(settings: Settings | None = None) -> Path:
    """Promoted models (Phase E) — never wiped by cleanup-local-data."""
    path = get_local_dir(settings) / "models" / "approved"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_analytics_dir(settings: Settings | None = None) -> Path:
    """Phase H analytics snapshots (separate from app.db — INV-7)."""
    path = get_local_dir(settings) / "analytics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_analytics_db_path(settings: Settings | None = None) -> Path:
    """SQLite file for metric snapshots / snapshot_runs (WAL)."""
    return get_analytics_dir(settings) / "analytics.db"


# Directories that cleanup-local-data.ps1 must never delete.
CLEANUP_PRESERVE_RELATIVE = (
    "team_memory",
    "knowledge",
    "models/approved",
    "eval",
    "analytics",
)


def ensure_local_structure(settings: Settings | None = None) -> None:
    """Create Phase 1+2 (+ Phase D prep) local storage folders."""
    local = get_local_dir(settings)
    for name in (
        "backlog",
        "semantic",
        "exports",
        "samples",
        "knowledge",
        "feedback",
        "briefings",
        "themes",
        "team_memory",
        "logs",
        "local_data",  # Phase E scratch (parquet / job models) — convention only in Phase D
        "models",
        "eval",  # Phase G3 golden questions + results
        "analytics",  # Phase H metric snapshots (analytics.db)
    ):
        (local / name).mkdir(parents=True, exist_ok=True)

    (local / "knowledge" / "themes").mkdir(parents=True, exist_ok=True)
    (local / "knowledge" / "curriculum").mkdir(parents=True, exist_ok=True)
    (local / "briefings" / "digests").mkdir(parents=True, exist_ok=True)
    (local / "models" / "approved").mkdir(parents=True, exist_ok=True)
    (local / "eval" / "results").mkdir(parents=True, exist_ok=True)

    for rel, default in (
        ("semantic/trusted.json", '{"version": "1.0", "metrics": []}'),
        ("semantic/draft.json", '{"version": "1.0", "metrics": []}'),
        ("knowledge/glossary.json", '{"version": "1.0", "items": []}'),
        ("knowledge/targets.json", '{"version": "1.0", "items": []}'),
        ("knowledge/relationships.json", '{"version": "1.0", "items": []}'),
        ("knowledge/metric_registry.json", '{"version": "1.0", "metrics": []}'),
    ):
        path = local / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(default, encoding="utf-8")

    sql_ref = local / "knowledge" / "sql_reference"
    for sub in (
        "SAPHANADB/Tables",
        "SAPHANADB/StoredProcedures",
    ):
        (sql_ref / sub).mkdir(parents=True, exist_ok=True)

    manifest_path = sql_ref / "_manifest.json"
    if not manifest_path.exists():
        template_path = get_templates_dir(settings) / "sql_reference" / "_manifest.template.json"
        if template_path.exists():
            data = json.loads(template_path.read_text(encoding="utf-8"))
            data["items"] = []
            manifest_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        else:
            manifest_path.write_text(
                '{"version": "1.0", "warehouse": "WH_Silver", "items": []}\n',
                encoding="utf-8",
            )
