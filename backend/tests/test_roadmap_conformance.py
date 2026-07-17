"""Conformance guard for the Phase G→K roadmap (delegation guardrails).

Mechanical half of knowledge/05-architecture/phases/phase-g-to-k-grand-roadmap.md §4:
invariants about modules that do not exist yet are SKIPPED, and start enforcing
automatically the moment the module is created. Renaming any canonical module or
function listed in §4.2 requires owner approval and must update the roadmap and
this file in the same commit.
"""

import ast
import re
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
APP_DIR = BACKEND_DIR / "app"
SERVICES_DIR = APP_DIR / "services"
ANALYTICS_DIR = APP_DIR / "analytics"
PHASES_DIR = REPO_ROOT / "knowledge" / "05-architecture" / "phases"
GATES_DIR = PHASES_DIR / "gates"

# INV-1: no vector DB / message queue / hard-to-build forecasting libs
FORBIDDEN_DEPS = (
    "prophet",
    "chromadb",
    "faiss",
    "qdrant",
    "weaviate",
    "pgvector",
    "redis",
    "celery",
)

# INV-2: backend/app/analytics/* must be pure (offline-testable, no I/O, no LLM)
ANALYTICS_PURITY_BANNED = (
    "httpx",
    "requests",
    "aiohttp",
    "langchain",
    "langchain_core",
    "langchain_ollama",
    "langchain_community",
    "langgraph",
    "ollama",
    "anthropic",
    "psycopg2",
    "pyodbc",
    "sqlite3",
    "sqlalchemy",
    "fastapi",
    "streamlit",
    "app.services",
    "app.agents",
    "app.api",
    "app.db",
)

# Canonical new services introduced by phases G–K (roadmap §4.2)
ROADMAP_SERVICES = (
    "metric_registry.py",
    "progress_reporter.py",
    "eval_service.py",
    "snapshot_store.py",
    "snapshot_refresh_service.py",
    "insight_store.py",
    "insight_pipeline.py",
    "scheduler_service.py",
    "embedding_service.py",
    "sql_pattern_store.py",
    "lesson_miner.py",
    "insight_ranker.py",
    "digest_service.py",
)

# INV-7: analytics-side services may only touch analytics.db, never app.db
ANALYTICS_DB_ONLY_SERVICES = (
    "snapshot_store.py",
    "snapshot_refresh_service.py",
    "insight_store.py",
    "insight_pipeline.py",
    "scheduler_service.py",
)


def _imports_of(path: Path) -> set[str]:
    """All imported module paths in a file, with relative imports resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    pkg = path.relative_to(BACKEND_DIR).with_suffix("").parts[:-1]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - node.level + 1]
                if node.module:
                    found.add(".".join((*base, node.module)))
                else:
                    found.update(".".join((*base, alias.name)) for alias in node.names)
            elif node.module:
                found.add(node.module)
    return found


def _violations(imports: set[str], banned: tuple[str, ...]) -> set[str]:
    return {
        imp
        for imp in imports
        for b in banned
        if imp == b or imp.startswith(b + ".")
    }


def _require_service(name: str, phase: str) -> Path:
    path = SERVICES_DIR / name
    if not path.exists():
        pytest.skip(f"{phase}: {name} not created yet — invariant not applicable")
    return path


# ---------------------------------------------------------------------------
# Always-on invariants (must pass from day one)
# ---------------------------------------------------------------------------


def test_inv1_no_forbidden_dependencies():
    lines = [
        line.split("#")[0].strip().lower()
        for line in (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    ]
    offenders = {
        dep: [line for line in lines if line.startswith(dep)]
        for dep in FORBIDDEN_DEPS
        if any(line.startswith(dep) for line in lines)
    }
    assert not offenders, (
        f"INV-1: forbidden dependencies in backend/requirements.txt: {offenders} "
        "(roadmap §4.1 — no vector DB / queue / prophet)"
    )


def test_governance_artifacts_exist():
    roadmap = PHASES_DIR / "phase-g-to-k-grand-roadmap.md"
    template = PHASES_DIR / "_TEMPLATE-phase.md"
    gates_readme = GATES_DIR / "README.md"
    missing = [str(p) for p in (roadmap, template, gates_readme) if not p.exists()]
    assert not missing, (
        f"Delegation governance artifacts missing (do not delete/rename them): {missing}"
    )


# ---------------------------------------------------------------------------
# Conditional invariants (skip until the module exists, then enforce forever)
# ---------------------------------------------------------------------------


def test_inv2_analytics_modules_are_pure():
    if not ANALYTICS_DIR.exists():
        pytest.skip("Phase H not started: backend/app/analytics/ does not exist yet")
    offenders = {}
    for py in sorted(ANALYTICS_DIR.rglob("*.py")):
        bad = _violations(_imports_of(py), ANALYTICS_PURITY_BANNED)
        if bad:
            offenders[str(py.relative_to(BACKEND_DIR))] = sorted(bad)
    assert not offenders, (
        f"INV-2: backend/app/analytics/ must stay pure (no I/O/LLM imports): {offenders}"
    )


def test_inv3_snapshot_refresh_sql_comes_from_metric_registry():
    path = _require_service("snapshot_refresh_service.py", "Phase H")
    imports = _imports_of(path)
    source = path.read_text(encoding="utf-8")
    assert any("metric_registry" in imp for imp in imports), (
        "INV-3: snapshot_refresh_service.py must import from metric_registry"
    )
    assert "render_metric_sql" in source, (
        "INV-3: snapshot_refresh_service.py must render scheduled SQL via render_metric_sql"
    )
    assert "make_chat_ollama" not in source and not _violations(imports, ("app.core.llm",)), (
        "INV-3: scheduled SQL must be deterministic — no LLM in the refresh path"
    )


def test_inv4_insight_narration_is_validated():
    path = _require_service("insight_pipeline.py", "Phase I")
    source = path.read_text(encoding="utf-8")
    assert "validate_narrative_numbers" in source, (
        "INV-4: insight_pipeline.py must run every narrative through "
        "validate_narrative_numbers (evidence-first principle)"
    )


def test_inv5_eval_grading_is_deterministic():
    path = _require_service("eval_service.py", "Phase G3")
    imports = _imports_of(path)
    source = path.read_text(encoding="utf-8")
    bad = _violations(imports, ("anthropic", "app.core.llm"))
    assert not bad and "make_chat_ollama" not in source, (
        f"INV-5: eval_service.py must not use an LLM for grading (found: {sorted(bad) or 'make_chat_ollama'}); "
        "the LLM is the examinee, never the grader"
    )


def test_inv6_scheduler_delegates_to_job_runner():
    path = _require_service("scheduler_service.py", "Phase I")
    imports = _imports_of(path)
    assert any("job_runner" in imp for imp in imports), (
        "INV-6: scheduler_service.py must enqueue work through job_runner"
    )
    bad = _violations(imports, ("threading", "multiprocessing", "subprocess"))
    assert not bad, (
        f"INV-6: scheduler_service.py must not spawn its own execution paths: {sorted(bad)}"
    )


def test_inv7_analytics_services_never_touch_app_db():
    existing = [SERVICES_DIR / n for n in ANALYTICS_DB_ONLY_SERVICES if (SERVICES_DIR / n).exists()]
    if not existing:
        pytest.skip("Phase H/I not started: no analytics-side services yet")
    offenders = [p.name for p in existing if "app.db" in p.read_text(encoding="utf-8")]
    assert not offenders, (
        f"INV-7: analytics-side services must only use analytics.db, never app.db: {offenders}"
    )


def test_inv8_ranker_gates_are_declared():
    path = _require_service("insight_ranker.py", "Phase J")
    source = path.read_text(encoding="utf-8")
    assert re.search(r"MIN_LABELS_FOR_ML\s*=\s*100\b", source), (
        "INV-8: insight_ranker.py must declare MIN_LABELS_FOR_ML = 100"
    )
    assert re.search(r"MIN_AUC_GATE\s*=\s*0\.6\b", source), (
        "INV-8: insight_ranker.py must declare MIN_AUC_GATE = 0.6"
    )


def test_inv9_new_services_use_run_sql_not_raw_drivers():
    existing = [SERVICES_DIR / n for n in ROADMAP_SERVICES if (SERVICES_DIR / n).exists()]
    if not existing:
        pytest.skip("Phases G–K not started: no roadmap services yet")
    offenders = {
        p.name: sorted(bad)
        for p in existing
        if (bad := _violations(_imports_of(p), ("psycopg2", "pyodbc")))
    }
    assert not offenders, (
        f"INV-9: roadmap services must go through fabric_sql.run_sql (guards + provenance), "
        f"never raw drivers: {offenders}"
    )


def test_inv11_baseline_recorded_before_analytics_engine():
    if not ANALYTICS_DIR.exists():
        pytest.skip("Phase H not started: backend/app/analytics/ does not exist yet")
    gate = GATES_DIR / "G3-baseline-recorded.md"
    assert gate.exists(), (
        "INV-11: record the golden-question baseline first — "
        "knowledge/05-architecture/phases/gates/G3-baseline-recorded.md must exist "
        "before backend/app/analytics/ is created (measure before getting smarter)"
    )
