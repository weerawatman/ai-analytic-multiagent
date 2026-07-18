"""Role curriculum store — self-development question banks (Phase K).

Canonical path: ``data/local/knowledge/curriculum/{role}.json``.
Progress is numeric pass-rate, never marketing copy.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.services.local_paths import get_local_dir, get_templates_dir

ROLES = (
    "data_analyst",
    "data_scientist",
    "data_engineer",
    "business_analyst",
)

# Seed banks — professional self-questions per role (roadmap §10).
_SEED: dict[str, list[dict[str, Any]]] = {
    "data_analyst": [
        {
            "id": "da-001",
            "question_th": "ยอดขายรวมรายไตรมาสล่าสุดเป็นเท่าใด และ QoQ เปลี่ยนไปเท่าไร",
            "topic": "revenue_quarterly",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "da-002",
            "question_th": "Gross Profit และ Net Profit รายไตรมาสล่าสุดเป็นเท่าใด",
            "topic": "gp_np_quarterly",
            "expected_metric_key": "metric.gross_profit",
            "golden_question_id": None,
        },
        {
            "id": "da-003",
            "question_th": "ยอดขายต่อลูกค้าเฉลี่ยในช่วงล่าสุดเป็นเท่าใด",
            "topic": "sales_per_customer",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "da-004",
            "question_th": "สินค้าหรือกลุ่มสินค้าที่เป็น champion ตามยอดขายคืออะไร",
            "topic": "product_champion",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
        {
            "id": "da-005",
            "question_th": "อัตราส่วนลด (discount rate) ต่อลูกค้าเป็นอย่างไร",
            "topic": "discount_rate",
            "expected_metric_key": "metric.discount_rate",
            "golden_question_id": None,
        },
        {
            "id": "da-006",
            "question_th": "เปรียบเทียบยอดขาย YoY ไตรมาสเดียวกันปีก่อน",
            "topic": "yoy",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "da-007",
            "question_th": "มีความผิดปกติของยอดขายในช่วงล่าสุดหรือไม่",
            "topic": "anomaly_sales",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "da-008",
            "question_th": "ลูกค้าที่เพิ่มขึ้นและหายไปในช่วงล่าสุดมีกี่ราย",
            "topic": "customer_churn_growth",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
    ],
    "data_scientist": [
        {
            "id": "ds-001",
            "question_th": "ยอดขายมี seasonality ชัดเจนหรือไม่ และช่วงไหนสูงสุด",
            "topic": "seasonality",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "ds-002",
            "question_th": "driver หลักที่อธิบายการเปลี่ยนแปลงยอดขายในช่วงล่าสุดคืออะไร",
            "topic": "driver_analysis",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "ds-003",
            "question_th": "มี anomaly หรือ changepoint ใน series รายได้หรือไม่",
            "topic": "anomaly_detection",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
    ],
    "data_engineer": [
        {
            "id": "de-001",
            "question_th": "คุณภาพข้อมูลหลัก (null rate / grain) ของตารางขายเป็นอย่างไร",
            "topic": "data_quality",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
        {
            "id": "de-002",
            "question_th": "ความสดของข้อมูล (freshness) ล่าสุดของ metric snapshots เป็นอย่างไร",
            "topic": "freshness",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
        {
            "id": "de-003",
            "question_th": "มีคอลัมน์หรือ join ที่น่าสงสัยใน pipeline หรือไม่",
            "topic": "pipeline_integrity",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
    ],
    "business_analyst": [
        {
            "id": "ba-001",
            "question_th": "เป้า vs จริงของยอดขายในช่วงล่าสุดต่างกันเท่าไร",
            "topic": "target_vs_actual",
            "expected_metric_key": "metric.revenue",
            "golden_question_id": None,
        },
        {
            "id": "ba-002",
            "question_th": "สรุปเรื่องราวผู้บริหาร 3 ประเด็นจากตัวเลขล่าสุด",
            "topic": "executive_story",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
        {
            "id": "ba-003",
            "question_th": "KPI ใดควรนำเสนอใน board pack สัปดาห์นี้",
            "topic": "board_kpi",
            "expected_metric_key": None,
            "golden_question_id": None,
        },
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def curriculum_dir() -> Path:
    path = get_local_dir() / "knowledge" / "curriculum"
    path.mkdir(parents=True, exist_ok=True)
    return path


def curriculum_path(role: str) -> Path:
    if role not in ROLES:
        raise ValueError(f"Unknown curriculum role: {role!r}")
    return curriculum_dir() / f"{role}.json"


def _empty_question(seed: dict[str, Any]) -> dict[str, Any]:
    return {
        **seed,
        "status": "pending",  # pending | studied | passed | failed
        "attempts": 0,
        "passed_count": 0,
        "last_studied_at": None,
        "last_result": None,
    }


def _recompute_stats(questions: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = sum(1 for q in questions if int(q.get("attempts") or 0) > 0)
    # A question "passes" curriculum when last_result.passed is True OR status==passed
    passed = sum(
        1
        for q in questions
        if q.get("status") == "passed"
        or (isinstance(q.get("last_result"), dict) and q["last_result"].get("passed"))
    )
    # Prefer questions that have been studied at least once for pass-rate denominator
    denom = attempted or 0
    pass_rate = round(100.0 * passed / denom, 2) if denom else 0.0
    return {
        "question_count": len(questions),
        "attempted": attempted,
        "passed": passed,
        "pass_rate_pct": pass_rate,
    }


def seed_curriculum(role: str, *, force: bool = False) -> dict[str, Any]:
    path = curriculum_path(role)
    if path.exists() and not force:
        return load_curriculum(role)
    questions = [_empty_question(dict(s)) for s in _SEED.get(role, [])]
    doc = {
        "version": "1.0",
        "role": role,
        "updated_at": _utc_now(),
        "questions": questions,
        "stats": _recompute_stats(questions),
    }
    _write(path, doc)
    return doc


def ensure_all_curricula(*, force: bool = False) -> dict[str, dict[str, Any]]:
    # Copy template dir marker if present (optional)
    tpl = get_templates_dir() / "curriculum"
    if tpl.exists():
        curriculum_dir()
    return {role: seed_curriculum(role, force=force) for role in ROLES}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_curriculum(role: str) -> dict[str, Any]:
    path = curriculum_path(role)
    if not path.exists():
        return seed_curriculum(role)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["stats"] = _recompute_stats(list(doc.get("questions") or []))
    return doc


def save_curriculum(doc: dict[str, Any]) -> dict[str, Any]:
    role = doc["role"]
    doc["stats"] = _recompute_stats(list(doc.get("questions") or []))
    doc["updated_at"] = _utc_now()
    _write(curriculum_path(role), doc)
    return doc


def pick_due_questions(role: str, *, n: int = 2) -> list[dict[str, Any]]:
    """Prefer never-attempted, then oldest last_studied_at."""
    doc = load_curriculum(role)
    questions = list(doc.get("questions") or [])

    def sort_key(q: dict[str, Any]) -> tuple:
        attempts = int(q.get("attempts") or 0)
        last = q.get("last_studied_at") or ""
        return (attempts, last)

    ordered = sorted(questions, key=sort_key)
    return ordered[: max(0, n)]


def record_attempt(
    role: str,
    question_id: str,
    *,
    answer_excerpt: str,
    passed: bool | None,
    golden_match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = load_curriculum(role)
    questions = list(doc.get("questions") or [])
    found = False
    for q in questions:
        if q.get("id") != question_id:
            continue
        found = True
        q["attempts"] = int(q.get("attempts") or 0) + 1
        q["last_studied_at"] = _utc_now()
        q["last_result"] = {
            "passed": passed,
            "answer_excerpt": (answer_excerpt or "")[:1000],
            "golden_match": golden_match,
            "at": q["last_studied_at"],
        }
        if passed is True:
            q["status"] = "passed"
            q["passed_count"] = int(q.get("passed_count") or 0) + 1
        elif passed is False:
            q["status"] = "failed"
        else:
            q["status"] = "studied"
        break
    if not found:
        raise KeyError(f"Curriculum question not found: {role}/{question_id}")
    doc["questions"] = questions
    return save_curriculum(doc)


def match_golden_question(
    curriculum_q: dict[str, Any],
    golden_questions: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Match by explicit id, else by expected_metric_key."""
    from backend.app.services import eval_service

    goldens = golden_questions if golden_questions is not None else eval_service.load_golden_questions()
    gid = curriculum_q.get("golden_question_id")
    if gid:
        for g in goldens:
            if g.get("id") == gid:
                return g
    metric = curriculum_q.get("expected_metric_key")
    if metric:
        for g in goldens:
            if g.get("expected_metric_key") == metric and g.get("active", True):
                return g
    return None


def pass_rate_summary() -> dict[str, Any]:
    ensure_all_curricula()
    roles: dict[str, Any] = {}
    for role in ROLES:
        stats = load_curriculum(role).get("stats") or {}
        roles[role] = stats
    attempted = sum(int(s.get("attempted") or 0) for s in roles.values())
    passed = sum(int(s.get("passed") or 0) for s in roles.values())
    overall = round(100.0 * passed / attempted, 2) if attempted else 0.0
    return {"roles": roles, "overall_pass_rate_pct": overall, "attempted": attempted, "passed": passed}


def append_study_result_to_memory(
    theme_id: str,
    *,
    role: str,
    curriculum_question_id: str,
    question_th: str,
    answer_excerpt: str,
    golden_match: dict[str, Any] | None = None,
    theme_name: str = "",
) -> dict[str, Any]:
    """Store study output in team memory pending CEO approve (HITL)."""
    from backend.app.services.team_memory_store import get_or_create_team_memory, save_team_memory

    data = get_or_create_team_memory(theme_id, theme_name)
    results = data.setdefault("study_results", [])
    entry = {
        "id": uuid4().hex,
        "role": role,
        "curriculum_question_id": curriculum_question_id,
        "question_th": question_th,
        "answer_excerpt": (answer_excerpt or "")[:2000],
        "status": "pending_ceo_approve",
        "golden_match": golden_match,
        "studied_at": _utc_now(),
    }
    results.append(entry)
    data["study_results"] = results[-50:]
    return save_team_memory(data)


def approve_study_result(theme_id: str, result_id: str, *, approved: bool) -> dict[str, Any]:
    from backend.app.services.team_memory_store import load_team_memory, save_team_memory

    data = load_team_memory(theme_id)
    if not data:
        raise KeyError(f"No team memory for theme {theme_id}")
    found = False
    for item in data.get("study_results") or []:
        if item.get("id") != result_id:
            continue
        item["status"] = "approved" if approved else "rejected"
        item["reviewed_at"] = _utc_now()
        found = True
        break
    if not found:
        raise KeyError(f"Study result not found: {result_id}")
    return save_team_memory(data)
