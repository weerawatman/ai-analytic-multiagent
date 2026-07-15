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
    """Create Phase 1 local storage folders."""
    local = get_local_dir(settings)
    for name in ("backlog", "semantic", "exports", "samples"):
        (local / name).mkdir(parents=True, exist_ok=True)

    semantic_trusted = local / "semantic" / "trusted.json"
    if not semantic_trusted.exists():
        semantic_trusted.write_text('{"version": "1.0", "metrics": []}', encoding="utf-8")

    semantic_draft = local / "semantic" / "draft.json"
    if not semantic_draft.exists():
        semantic_draft.write_text('{"version": "1.0", "metrics": []}', encoding="utf-8")
