"""Phase 1 Definition of Done — automated validation checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.services import backlog_store
from backend.app.services.fabric_connector import get_fabric_connector
from backend.app.services.local_paths import get_local_dir, get_project_root
from backend.app.services.report_generator import render_handoff_markdown
from backend.app.services.semantic_store import read_trusted_layer
from backend.app.services.sql_guard import SQLGuardError, validate_read_only_sql

QUALITY_BAR_FIELDS = (
    "question_th",
    "answer_summary_th",
    "sql_primary",
    "assumptions",
    "confidence",
    "unknowns",
    "questions_for_ba_da",
)


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


def _check_sql_guard() -> dict[str, Any]:
    blocked = False
    try:
        validate_read_only_sql("INSERT INTO t VALUES (1)")
    except SQLGuardError:
        blocked = True

    allowed = False
    try:
        validate_read_only_sql("SELECT 1")
        allowed = True
    except SQLGuardError:
        pass

    passed = blocked and allowed
    return _check(
        "AC-1-guard",
        "SQL guard blocks writes, allows SELECT",
        passed,
        "INSERT blocked" if blocked else "INSERT not blocked",
    )


async def _check_fabric_connection() -> dict[str, Any]:
    connector = get_fabric_connector()
    if not connector.is_configured():
        return _check(
            "AC-1-fabric",
            "Fabric DW connected (Service Principal)",
            False,
            "Fabric not configured in .env",
            manual_note="Set FABRIC_* vars and verify /api/v1/fabric/health",
        )
    try:
        ping = connector.ping()
        return _check(
            "AC-1-fabric",
            "Fabric DW connected (Service Principal)",
            True,
            f"Connected to {ping.get('database', 'WH_SAP_PRD')}",
        )
    except Exception as exc:
        return _check(
            "AC-1-fabric",
            "Fabric DW connected (Service Principal)",
            False,
            str(exc),
            manual_note="Fix SP credentials or network, then re-run validation",
        )


def _check_gitignore_local() -> dict[str, Any]:
    gitignore = get_project_root() / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    passed = "data/local/" in text
    return _check(
        "AC-10",
        "data/local/ gitignored",
        passed,
        "Found data/local/ in .gitignore" if passed else "Missing data/local/ in .gitignore",
    )


def _check_templates_committed() -> dict[str, Any]:
    templates = get_project_root() / "data" / "templates"
    backlog_tpl = templates / "backlog_item.template.json"
    semantic_tpl = templates / "semantic_layer.template.json"
    passed = backlog_tpl.exists() and semantic_tpl.exists()
    return _check(
        "DoD-templates",
        "JSON templates committed under data/templates/",
        passed,
        f"Templates present: {passed}",
    )


def _check_local_storage() -> dict[str, Any]:
    local = get_local_dir()
    required = ["backlog", "semantic", "exports"]
    missing = [name for name in required if not (local / name).exists()]
    passed = not missing
    return _check(
        "AC-9",
        "Local JSON + SQLite storage initialized",
        passed,
        "All dirs exist" if passed else f"Missing: {', '.join(missing)}",
    )


def _check_backlog_quality_item() -> dict[str, Any]:
    items = backlog_store.list_items()
    if not items:
        return _check(
            "AC-4",
            "≥1 insight candidate with Quality Bar D fields",
            False,
            "No backlog items yet",
            manual_note="Run Explore session, save candidate from sidebar",
        )

    complete = []
    for item in items:
        gaps = [f for f in QUALITY_BAR_FIELDS if not item.get(f)]
        has_alt_or_sample = item.get("sql_alternative") or item.get("sample_data_ref")
        if not gaps and has_alt_or_sample:
            complete.append(item)

    passed = len(complete) >= 1
    detail = f"{len(complete)}/{len(items)} items pass Quality Bar D"
    return _check("AC-4", "≥1 insight candidate with Quality Bar D fields", passed, detail)


def _check_export_capability() -> dict[str, Any]:
    items = backlog_store.list_items()
    if not items:
        return _check(
            "AC-5",
            "Thai Markdown handoff export works",
            False,
            "No backlog items to export",
            manual_note="Save backlog item then export from sidebar",
        )

    try:
        content = render_handoff_markdown(items[0])
        passed = "รายงาน Insight Candidate" in content and "```sql" in content
        return _check(
            "AC-5",
            "Thai Markdown handoff export works",
            passed,
            "Report template renders with SQL block" if passed else "Template incomplete",
        )
    except Exception as exc:
        return _check("AC-5", "Thai Markdown handoff export works", False, str(exc))


def _check_ba_da_feedback() -> dict[str, Any]:
    items = backlog_store.list_items()
    with_feedback = [
        i
        for i in items
        if i.get("ba_da_feedback") or i.get("status") in {"validated", "discussing", "promoted"}
    ]
    passed = len(with_feedback) >= 1
    return _check(
        "AC-6",
        "BA/DA feedback recorded on backlog item",
        passed,
        f"{len(with_feedback)} item(s) with feedback or validated status",
        manual_note="Record feedback in backlog sidebar after BA/DA discussion",
    )


async def _check_trusted_promotion() -> dict[str, Any]:
    trusted = await read_trusted_layer()
    metrics = trusted.get("metrics") or []
    complete = [
        m
        for m in metrics
        if m.get("playbook_th") and m.get("example_questions_th") and m.get("sql_template")
    ]
    promoted_backlog = backlog_store.list_items(status="promoted")
    passed = len(complete) >= 1 and len(promoted_backlog) >= 1
    return _check(
        "AC-7",
        "≥1 Trusted entry with playbook + example questions",
        passed,
        f"{len(complete)} trusted metric(s), {len(promoted_backlog)} promoted backlog item(s)",
        manual_note="Validate backlog item → Promote to Trusted → Approve HITL",
    )


async def _check_trusted_mode_ready() -> dict[str, Any]:
    trusted = await read_trusted_layer()
    passed = len(trusted.get("metrics") or []) >= 1
    return _check(
        "AC-8",
        "Trusted mode can reference approved definitions",
        passed,
        f"{len(trusted.get('metrics') or [])} trusted definition(s) loaded",
        manual_note="Switch to Trusted mode and ask a question about promoted metric",
    )


def _check_exports_on_disk() -> dict[str, Any]:
    exports_dir = get_local_dir() / "exports"
    md_files = list(exports_dir.glob("*.md")) if exports_dir.exists() else []
    passed = len(md_files) >= 1
    return _check(
        "DoD-export-file",
        "Export file saved under data/local/exports/",
        passed,
        f"{len(md_files)} export file(s)" if passed else "No .md exports yet",
        manual_note="Click Export รายงาน on a backlog item",
    )


def _check_theme_cycle() -> dict[str, Any]:
    items = backlog_store.list_items()
    themes = {i.get("theme") for i in items if i.get("theme")}
    passed = len(themes) >= 1
    return _check(
        "DoD-theme",
        "One theme cycle documented in backlog",
        passed,
        f"Themes in backlog: {', '.join(sorted(themes)) or '(none)'}",
        manual_note="Pick theme from schema scan and save insights under that theme",
    )


async def run_phase1_validation() -> dict[str, Any]:
    """Run all Phase 1 DoD checks and return structured report."""
    checks = [
        _check_sql_guard(),
        await _check_fabric_connection(),
        _check_local_storage(),
        _check_gitignore_local(),
        _check_templates_committed(),
        _check_backlog_quality_item(),
        _check_export_capability(),
        _check_exports_on_disk(),
        _check_ba_da_feedback(),
        await _check_trusted_promotion(),
        await _check_trusted_mode_ready(),
        _check_theme_cycle(),
    ]

    passed_count = sum(1 for c in checks if c["passed"])
    automated = [c for c in checks if c["automated"]]
    automated_passed = sum(1 for c in automated if c["passed"])

    return {
        "phase": "1",
        "summary": {
            "passed": passed_count,
            "total": len(checks),
            "automated_passed": automated_passed,
            "automated_total": len(automated),
            "ready_for_signoff": passed_count == len(checks),
        },
        "checks": checks,
        "sign_off_doc": "knowledge/07-testing/sign-off.md",
    }
