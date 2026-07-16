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


def ensure_local_structure(settings: Settings | None = None) -> None:
    """Create Phase 1+2 local storage folders."""
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
    ):
        (local / name).mkdir(parents=True, exist_ok=True)

    (local / "knowledge" / "themes").mkdir(parents=True, exist_ok=True)

    for rel, default in (
        ("semantic/trusted.json", '{"version": "1.0", "metrics": []}'),
        ("semantic/draft.json", '{"version": "1.0", "metrics": []}'),
        ("knowledge/glossary.json", '{"version": "1.0", "items": []}'),
        ("knowledge/targets.json", '{"version": "1.0", "items": []}'),
        ("knowledge/relationships.json", '{"version": "1.0", "items": []}'),
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
