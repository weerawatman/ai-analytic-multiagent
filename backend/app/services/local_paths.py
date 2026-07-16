"""Resolve local data directory paths and ensure structure exists."""

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
    for name in ("backlog", "semantic", "exports", "samples", "knowledge", "feedback", "briefings", "themes"):
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
