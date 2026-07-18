"""Golden-question evaluation harness (Phase G3).

Grading is deterministic: extract numbers from the examinee answer and compare
to a reference rendered from the Metric Registry on the same SQL source.
The LLM is the examinee — never the grader (INV-5).
"""

from __future__ import annotations

import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from backend.app.services.local_paths import get_local_dir, get_templates_dir

# Number patterns: 1,234.56 / 1234.56 / 1.2M Thai-ish
_NUM_RE = re.compile(
    r"(?<![\w.])(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)(?![\w.])"
)

AnswerFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def eval_dir() -> Path:
    path = get_local_dir() / "eval"
    path.mkdir(parents=True, exist_ok=True)
    (path / "results").mkdir(parents=True, exist_ok=True)
    return path


def golden_questions_path() -> Path:
    return eval_dir() / "golden_questions.json"


def results_dir() -> Path:
    return eval_dir() / "results"


def load_golden_questions(*, active_only: bool = True) -> list[dict[str, Any]]:
    path = golden_questions_path()
    if not path.exists():
        tpl = get_templates_dir() / "eval" / "golden_questions.template.json"
        if tpl.exists():
            path.write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = list(doc.get("questions") or [])
    if active_only:
        items = [q for q in items if q.get("active", True)]
    return items


def extract_numbers(text: str) -> list[float]:
    """Pull numeric literals from an answer string (comma thousands OK)."""
    out: list[float] = []
    for m in _NUM_RE.finditer(text or ""):
        raw = m.group(1).replace(",", "")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def numbers_within_tolerance(
    actual: list[float],
    expected: float,
    tolerance_pct: float,
) -> bool:
    if not actual:
        return False
    if expected == 0:
        return any(abs(a) <= abs(tolerance_pct) for a in actual)
    tol = abs(expected) * (tolerance_pct / 100.0)
    return any(abs(a - expected) <= tol for a in actual)


def keywords_present(text: str, keywords: list[str]) -> bool:
    lowered = (text or "").lower()
    return all(k.lower() in lowered for k in keywords if k)


def grade_answer(
    question: dict[str, Any],
    *,
    answer_text: str,
    reference_value: float | None,
    sql_ok: bool,
    latency_s: float,
) -> dict[str, Any]:
    """Deterministic grade — no LLM."""
    nums = extract_numbers(answer_text)
    tol = float(question.get("tolerance_pct") or 1.0)
    keywords = list(question.get("expected_keywords_th") or [])
    kw_ok = keywords_present(answer_text, keywords) if keywords else True
    num_ok = (
        reference_value is not None
        and numbers_within_tolerance(nums, reference_value, tol)
    )
    passed = bool(sql_ok and num_ok and kw_ok)
    return {
        "passed": passed,
        "sql_ok": sql_ok,
        "number_match": num_ok,
        "keywords_ok": kw_ok,
        "extracted_numbers": nums[:10],
        "reference_value": reference_value,
        "tolerance_pct": tol,
        "latency_s": round(latency_s, 2),
    }


async def resolve_reference_value(
    question: dict[str, Any],
    *,
    run_sql_fn: Callable[..., Any] | None = None,
    get_source_fn: Callable[[], str] | None = None,
) -> tuple[float | None, str | None, str]:
    """Compute reference from metric registry + live SQL (or None if unavailable)."""
    from backend.app.services import metric_registry
    from backend.app.services.fabric_sql import get_active_sql_source, run_sql

    ref = question.get("reference") or {}
    if ref.get("kind") != "metric_registry":
        return None, None, "unsupported_reference_kind"

    metric_key = question.get("expected_metric_key")
    if not metric_key:
        return None, None, "missing_metric_key"

    entry = await metric_registry.get_metric(metric_key)
    if entry is None:
        return None, None, "metric_not_found"
    if entry.get("derived") or not entry.get("expression"):
        return None, None, "derived_or_no_expression"

    get_source = get_source_fn or get_active_sql_source
    source = get_source()
    if source == "offline":
        return None, None, "offline"

    sql = metric_registry.render_metric_sql(entry, source, limit=3)
    runner = run_sql_fn or run_sql
    try:
        result = runner(sql, mode="explore", max_rows=3, source=source)
    except Exception:
        return None, sql, "sql_error"

    rows = result.get("rows") or []
    if not rows:
        return None, sql, "empty_result"

    # Prefer metric_value column; else first numeric cell
    row0 = rows[0]
    if isinstance(row0, dict):
        if "metric_value" in row0 and row0["metric_value"] is not None:
            try:
                return float(row0["metric_value"]), sql, source
            except (TypeError, ValueError):
                pass
        for v in row0.values():
            try:
                return float(v), sql, source
            except (TypeError, ValueError):
                continue
    return None, sql, "parse_error"


def list_eval_runs(*, limit: int = 50) -> list[dict[str, Any]]:
    """Summaries of prior eval result files — newest first (Phase K trend chart)."""
    root = results_dir()
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "run_id": doc.get("run_id") or path.stem,
                "started_at": doc.get("started_at"),
                "finished_at": doc.get("finished_at"),
                "question_count": doc.get("question_count"),
                "passed": doc.get("passed"),
                "accuracy_pct": doc.get("accuracy_pct"),
                "sql_success_rate": doc.get("sql_success_rate"),
                "median_latency_s": doc.get("median_latency_s"),
                "harness_baseline": doc.get("harness_baseline", False),
                "elapsed_s": doc.get("elapsed_s"),
            }
        )
    # Stable chronological order for charts (oldest → newest)
    out.sort(key=lambda r: r.get("finished_at") or r.get("started_at") or "")
    return out


def eval_trend(*, limit: int = 50) -> dict[str, Any]:
    runs = list_eval_runs(limit=limit)
    return {
        "run_count": len(runs),
        "runs": runs,
        "latest_accuracy_pct": runs[-1]["accuracy_pct"] if runs else None,
        "first_accuracy_pct": runs[0]["accuracy_pct"] if runs else None,
    }


async def run_eval(
    questions: list[dict[str, Any]] | None = None,
    *,
    answer_fn: AnswerFn | None = None,
    run_id: str | None = None,
    harness_baseline: bool = False,
) -> dict[str, Any]:
    """Run golden questions through an answer function and grade deterministically.

    ``harness_baseline=True`` skips the chat pipeline and records empty answers
    (accuracy ~0) — useful when Ollama is unavailable; still produces a gateable
    baseline artifact proving the harness works.
    """
    qs = questions if questions is not None else load_golden_questions()
    run_id = run_id or uuid4().hex[:12]
    started = _utc_now()
    t0_all = time.perf_counter()

    results: list[dict[str, Any]] = []
    for q in qs:
        t0 = time.perf_counter()
        ref_val, ref_sql, ref_source = await resolve_reference_value(q)

        if harness_baseline or answer_fn is None:
            answer_text = ""
            sql_ok = False
            latency = time.perf_counter() - t0
        else:
            try:
                ans = await answer_fn(q)
                answer_text = str(ans.get("answer") or ans.get("content") or "")
                sql_ok = bool(ans.get("sql_ok", True))
                latency = float(ans.get("latency_s") or (time.perf_counter() - t0))
            except Exception as exc:
                answer_text = f"[eval error: {type(exc).__name__}]"
                sql_ok = False
                latency = time.perf_counter() - t0

        grade = grade_answer(
            q,
            answer_text=answer_text,
            reference_value=ref_val,
            sql_ok=sql_ok and ref_val is not None,
            latency_s=latency,
        )
        results.append(
            {
                "id": q.get("id"),
                "question_th": q.get("question_th"),
                "expected_metric_key": q.get("expected_metric_key"),
                "reference_sql": ref_sql,
                "reference_source": ref_source,
                "answer_excerpt": (answer_text or "")[:500],
                **grade,
            }
        )

    n = len(results) or 1
    passed = sum(1 for r in results if r["passed"])
    sql_ok_n = sum(1 for r in results if r["sql_ok"])
    latencies = [r["latency_s"] for r in results]
    summary = {
        "run_id": run_id,
        "started_at": started,
        "finished_at": _utc_now(),
        "elapsed_s": round(time.perf_counter() - t0_all, 2),
        "question_count": len(results),
        "passed": passed,
        "accuracy_pct": round(100.0 * passed / n, 2),
        "sql_success_rate": round(100.0 * sql_ok_n / n, 2),
        "median_latency_s": round(statistics.median(latencies), 2) if latencies else 0.0,
        "harness_baseline": harness_baseline or answer_fn is None,
        "results": results,
    }

    out_path = results_dir() / f"{run_id}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary["result_path"] = str(out_path)
    return summary
