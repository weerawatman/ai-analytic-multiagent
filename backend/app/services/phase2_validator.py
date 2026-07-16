"""Phase 2 Definition of Done — automated validation checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.services.local_paths import get_local_dir, get_project_root

SKILL_ROLES = ("data_engineer", "data_analyst", "data_scientist", "business_analyst")


def _check(
    check_id: str,
    title: str,
    passed: bool,
    detail: str,
    *,
    automated: bool = True,
    manual_note: str | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "passed": passed,
        "automated": automated,
        "detail": detail,
        "manual_note": manual_note,
    }


def _check_discovery_service() -> dict[str, Any]:
    path = get_project_root() / "backend" / "app" / "services" / "discovery_service.py"
    passed = path.exists()
    return _check(
        "P2-1-discovery",
        "Discovery service module exists",
        passed,
        str(path) if passed else "discovery_service.py missing",
    )


def _check_agent_skills() -> dict[str, Any]:
    base = get_project_root() / "backend" / "app" / "agents" / "skills"
    missing = [r for r in SKILL_ROLES if not (base / r / "SKILL.md").exists()]
    passed = not missing
    return _check(
        "P2-2-skills",
        "Agent SKILL.md files for all 4 roles",
        passed,
        f"Missing: {', '.join(missing)}" if missing else "All 4 skills present",
    )


def _check_knowledge_store() -> dict[str, Any]:
    local = get_local_dir()
    knowledge = local / "knowledge"
    files = ["glossary.json", "targets.json", "relationships.json"]
    existing = [f for f in files if (knowledge / f).exists()]
    passed = len(existing) == len(files)
    return _check(
        "P2-3-knowledge",
        "Knowledge store files (glossary, targets, relationships)",
        passed,
        f"{len(existing)}/{len(files)} files under {knowledge}",
    )


def _check_ba_agent() -> dict[str, Any]:
    path = get_project_root() / "backend" / "app" / "agents" / "business_analyst.py"
    passed = path.exists()
    return _check(
        "P2-4-ba",
        "Business Analyst agent node exists",
        passed,
        str(path) if passed else "business_analyst.py missing",
    )


def _check_collaborative_graph() -> dict[str, Any]:
    path = get_project_root() / "backend" / "app" / "agents" / "orchestrator.py"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    nodes = all(n in text for n in ("de_context", "business_analyst", "prepare_context"))
    passed = nodes
    return _check(
        "P2-5-graph",
        "Collaborative LangGraph pipeline wired",
        passed,
        "prepare_context → de_context → analyst → critique → BA → quality" if passed else "Missing nodes",
    )


def _check_phase2_apis() -> dict[str, Any]:
    main = get_project_root() / "backend" / "app" / "main.py"
    text = main.read_text(encoding="utf-8") if main.exists() else ""
    routes = all(r in text for r in ("discovery", "knowledge", "briefings", "feedback"))
    passed = routes
    return _check(
        "P2-6-api",
        "Phase 2 API routes registered",
        passed,
        "discovery, knowledge, briefings, feedback" if passed else "Missing route imports",
    )


def _check_frontend_panels() -> dict[str, Any]:
    root = get_project_root() / "frontend" / "components"
    panels = ["knowledge_panel.py", "ceo_briefing_panel.py", "theme_panel.py"]
    missing = [p for p in panels if not (root / p).exists()]
    passed = not missing
    return _check(
        "P2-7-ui",
        "Phase 2 UI panels (knowledge, CEO briefing, theme discovery)",
        passed,
        f"Missing: {', '.join(missing)}" if missing else "All panels present",
    )


def _check_discovery_cache_optional() -> dict[str, Any]:
    themes_dir = get_local_dir() / "knowledge" / "themes"
    discoveries = list(themes_dir.glob("*/discovery.json")) if themes_dir.exists() else []
    passed = len(discoveries) >= 1
    return _check(
        "P2-8-discovery-run",
        "At least one theme discovery cache on disk",
        passed,
        f"{len(discoveries)} discovery file(s)" if passed else "Run discovery by selecting a theme",
        manual_note="Select a theme in UI to trigger discovery pipeline",
    )


def _check_ceo_feedback_optional() -> dict[str, Any]:
    feedback_dir = get_local_dir() / "feedback"
    files = list(feedback_dir.glob("*.json")) if feedback_dir.exists() else []
    passed = len(files) >= 1
    return _check(
        "P2-9-feedback",
        "CEO feedback recorded for a theme",
        passed,
        f"{len(files)} feedback file(s)" if passed else "No CEO feedback yet",
        manual_note="Approve/reject a briefing item in CEO Briefing panel",
    )


def _check_knowledge_entries_optional() -> dict[str, Any]:
    glossary = get_local_dir() / "knowledge" / "glossary.json"
    count = 0
    if glossary.exists():
        import json

        doc = json.loads(glossary.read_text(encoding="utf-8"))
        count = len(doc.get("items", []))
    passed = count >= 1
    return _check(
        "P2-10-glossary",
        "At least one glossary entry (CEO/DE knowledge)",
        passed,
        f"{count} glossary item(s)" if passed else "Add field definition in Knowledge panel",
        manual_note="Add glossary entry e.g. VBRK.FKDAT = วันที่ billing",
    )


def _check_team_memory_optional() -> dict[str, Any]:
    memory_dir = get_local_dir() / "team_memory"
    files = list(memory_dir.glob("*.json")) if memory_dir.exists() else []
    passed = len(files) >= 1
    return _check(
        "P25-1-team-memory",
        "Team memory from onboarding (Phase 2.5)",
        passed,
        f"{len(files)} team_memory file(s)" if passed else "Select theme and complete onboarding",
        manual_note="Team Memory panel should show 4 role handoffs",
    )


def _check_onboarding_module() -> dict[str, Any]:
    paths = [
        get_project_root() / "backend" / "app" / "services" / "team_memory_store.py",
        get_project_root() / "backend" / "app" / "services" / "onboarding_service.py",
        get_project_root() / "backend" / "app" / "services" / "feedback_router.py",
        get_project_root() / "backend" / "app" / "agents" / "onboarding_graph.py",
    ]
    missing = [str(p.name) for p in paths if not p.exists()]
    passed = not missing
    return _check(
        "P25-2-modules",
        "Phase 2.5 onboarding + feedback router modules",
        passed,
        "All modules present" if passed else f"Missing: {', '.join(missing)}",
    )


def _check_team_memory_in_context() -> dict[str, Any]:
    path = get_project_root() / "backend" / "app" / "agents" / "context_nodes.py"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    passed = "team_memory_context" in text and "format_team_memory_context" in text
    return _check(
        "P25-3-context",
        "Team memory injected in agent context",
        passed,
        "team_memory_context wired" if passed else "Missing team memory in context_nodes",
    )


async def run_phase2_validation() -> dict[str, Any]:
    """Run all Phase 2 DoD checks and return structured report."""
    checks = [
        _check_discovery_service(),
        _check_agent_skills(),
        _check_knowledge_store(),
        _check_ba_agent(),
        _check_collaborative_graph(),
        _check_phase2_apis(),
        _check_frontend_panels(),
        _check_discovery_cache_optional(),
        _check_ceo_feedback_optional(),
        _check_knowledge_entries_optional(),
        _check_onboarding_module(),
        _check_team_memory_in_context(),
        _check_team_memory_optional(),
    ]

    passed_count = sum(1 for c in checks if c["passed"])
    automated = [c for c in checks if c["automated"]]
    automated_passed = sum(1 for c in automated if c["passed"])

    return {
        "phase": "2",
        "summary": {
            "passed": passed_count,
            "total": len(checks),
            "automated_passed": automated_passed,
            "automated_total": len(automated),
            "ready_for_signoff": passed_count == len(checks),
        },
        "checks": checks,
        "sign_off_doc": "knowledge/07-testing/phase-2-sign-off.md",
    }
