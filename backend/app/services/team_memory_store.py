"""Team memory — per-theme artifacts from role onboarding and feedback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.local_paths import get_local_dir

ROLE_ORDER = ("data_engineer", "data_analyst", "data_scientist", "business_analyst")

ROLE_LABELS_TH = {
    "data_engineer": "Data Engineer",
    "data_analyst": "Data Analyst",
    "data_scientist": "Data Scientist",
    "business_analyst": "Business Analyst",
}


def _memory_path(theme_id: str) -> Path:
    path = get_local_dir() / "team_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{theme_id}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_role() -> dict[str, Any]:
    return {
        "status": "pending",
        "handoff_summary": "",
        "artifact": {},
        "feedback_notes": [],
        "updated_at": None,
    }


def empty_team_memory(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    return {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "onboarded_at": None,
        "status": "pending",
        "team_summary": "",
        "recommended_tables": [],
        "key_metrics": [],
        "roles": {role: _empty_role() for role in ROLE_ORDER},
    }


def load_team_memory(theme_id: str) -> dict[str, Any] | None:
    path = _memory_path(theme_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_team_memory(data: dict[str, Any]) -> dict[str, Any]:
    theme_id = data["theme_id"]
    path = _memory_path(theme_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return data


def get_or_create_team_memory(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    existing = load_team_memory(theme_id)
    if existing:
        if theme_name and not existing.get("theme_name"):
            existing["theme_name"] = theme_name
        return existing
    return empty_team_memory(theme_id, theme_name)


def update_role_artifact(
    theme_id: str,
    role: str,
    *,
    handoff_summary: str,
    artifact: dict[str, Any],
    status: str = "completed",
    theme_name: str = "",
) -> dict[str, Any]:
    data = get_or_create_team_memory(theme_id, theme_name)
    roles = data.setdefault("roles", {})
    entry = roles.get(role, _empty_role())
    entry["handoff_summary"] = handoff_summary
    entry["artifact"] = artifact
    entry["status"] = status
    entry["updated_at"] = _utc_now()
    roles[role] = entry
    data["roles"] = roles
    return save_team_memory(data)


def append_role_feedback_note(
    theme_id: str,
    role: str,
    *,
    action: str,
    comment: str,
    brief_id: str = "",
) -> dict[str, Any]:
    data = get_or_create_team_memory(theme_id)
    roles = data.setdefault("roles", {})
    entry = roles.get(role, _empty_role())
    notes = entry.setdefault("feedback_notes", [])
    notes.append(
        {
            "action": action,
            "comment": comment,
            "brief_id": brief_id,
            "at": _utc_now(),
        }
    )
    entry["feedback_notes"] = notes[-20:]
    roles[role] = entry
    data["roles"] = roles
    return save_team_memory(data)


def finalize_team_memory(
    theme_id: str,
    *,
    team_summary: str,
    recommended_tables: list[str] | None = None,
    key_metrics: list[str] | None = None,
    status: str = "completed",
) -> dict[str, Any]:
    data = get_or_create_team_memory(theme_id)
    data["onboarded_at"] = _utc_now()
    data["status"] = status
    data["team_summary"] = team_summary
    if recommended_tables is not None:
        data["recommended_tables"] = recommended_tables
    if key_metrics is not None:
        data["key_metrics"] = key_metrics
    return save_team_memory(data)


def get_prior_handoffs(theme_id: str, before_role: str) -> str:
    """Collect handoff summaries from roles that run before `before_role`."""
    data = load_team_memory(theme_id)
    if not data:
        return ""
    try:
        idx = ROLE_ORDER.index(before_role)
    except ValueError:
        return ""
    lines: list[str] = []
    for role in ROLE_ORDER[:idx]:
        entry = data.get("roles", {}).get(role, {})
        summary = entry.get("handoff_summary", "")
        if summary:
            label = ROLE_LABELS_TH.get(role, role)
            lines.append(f"### {label}\n{summary}")
    return "\n\n".join(lines)


def format_team_memory_context(theme_id: str | None) -> str:
    if not theme_id:
        return ""
    data = load_team_memory(theme_id)
    if not data or data.get("status") not in ("completed", "running"):
        return "(team onboarding not completed — run onboarding after discovery)"

    lines: list[str] = ["## Team Memory (onboarding — use as shared baseline)"]
    if data.get("team_summary"):
        lines.append(f"**Team summary:** {data['team_summary']}")
    if data.get("recommended_tables"):
        lines.append(f"**Recommended tables:** {', '.join(data['recommended_tables'][:6])}")
    if data.get("key_metrics"):
        lines.append("**Key metrics:**")
        for m in data["key_metrics"][:8]:
            lines.append(f"- {m}")

    for role in ROLE_ORDER:
        entry = data.get("roles", {}).get(role, {})
        summary = entry.get("handoff_summary", "")
        if not summary:
            continue
        label = ROLE_LABELS_TH.get(role, role)
        lines.append(f"\n### {label} handoff\n{summary[:1200]}")
        notes = entry.get("feedback_notes") or []
        if notes:
            last = notes[-3:]
            lines.append("CEO feedback on this role:")
            for n in last:
                lines.append(f"- [{n.get('action')}] {n.get('comment', '')}")

    return "\n".join(lines)
