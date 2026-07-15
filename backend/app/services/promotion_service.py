"""Build and approve Trusted promotions from validated backlog items."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from backend.app.services import backlog_store
from backend.app.services.semantic_store import promote_metric


def _slugify(text: str, fallback: str = "metric") -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug[:48] or fallback


def _extract_grain(assumptions: list[str]) -> str:
    for assumption in assumptions:
        lower = assumption.lower()
        if lower.startswith("grain:"):
            return assumption.split(":", 1)[1].strip()
    return "unspecified"


def _extract_filters(assumptions: list[str]) -> list[str]:
    filters: list[str] = []
    for assumption in assumptions:
        lower = assumption.lower()
        if lower.startswith("filter:") or lower.startswith("filters:"):
            filters.append(assumption.split(":", 1)[1].strip())
    return filters


def build_metric_preview(item: dict[str, Any]) -> dict[str, Any]:
    """Build Trusted metric proposal from a backlog item."""
    theme = item.get("theme") or "general"
    question = item.get("question_th") or "metric"
    metric_key = f"{_slugify(theme)}_{_slugify(question, 'metric')}"

    assumptions = item.get("assumptions") or []
    questions = item.get("questions_for_ba_da") or []
    if not questions and question:
        questions = [question]

    playbook_lines = [
        "1) ตรวจ grain และ filter มาตรฐาน",
        "2) รัน SQL template และ sanity check",
        "3) เปรียบเทียบกับรายงาน BA/DA ที่ validate แล้ว",
    ]
    if item.get("sql_alternative"):
        playbook_lines.append("4) ใช้ SQL ทางเลือกเป็น sanity check")

    return {
        "metric_key": metric_key,
        "display_name_th": question[:120],
        "business_definition_th": item.get("answer_summary_th") or question,
        "sql_template": item.get("sql_primary") or "",
        "grain": _extract_grain(assumptions),
        "standard_filters": _extract_filters(assumptions),
        "validated_assumptions": assumptions,
        "playbook_th": "\n".join(playbook_lines),
        "example_questions_th": questions[:5],
        "theme": item.get("theme"),
        "source_backlog_id": item["id"],
    }


def render_preview_markdown(item: dict[str, Any], metric: dict[str, Any]) -> str:
    """Human-readable Thai preview for HITL approval."""
    lines = [
        f"# Preview — Promote to Trusted",
        "",
        f"**Backlog:** {item.get('question_th', '-')}",
        f"**Theme:** {item.get('theme') or '-'}",
        f"**Metric key:** `{metric['metric_key']}`",
        "",
        "## นิยามธุรกิจ",
        metric["business_definition_th"],
        "",
        "## SQL Template",
        "```sql",
        metric["sql_template"] or "-- ไม่มี SQL",
        "```",
        "",
        f"**Grain:** {metric['grain']}",
        "",
        "## Assumptions ที่ validate แล้ว",
    ]
    for assumption in metric.get("validated_assumptions") or ["- (ไม่ระบุ)"]:
        lines.append(f"- {assumption}")

    lines += ["", "## Playbook", metric["playbook_th"], "", "## ตัวอย่างคำถาม"]
    for question in metric.get("example_questions_th") or ["- (ไม่ระบุ)"]:
        lines.append(f"- {question}")

    lines += [
        "",
        "> กด Approve เพื่อเขียนลง `data/local/semantic/trusted.json` และเปลี่ยนสถานะ backlog เป็น `promoted`",
    ]
    return "\n".join(lines)


def get_promotion_preview(item_id: str) -> dict[str, Any]:
    item = backlog_store.get_item(item_id)
    if item is None:
        raise FileNotFoundError(f"Backlog item not found: {item_id}")

    if item.get("status") not in {"validated", "discussing"}:
        raise ValueError(
            f"Item status must be validated or discussing (current: {item.get('status')})"
        )

    metric = build_metric_preview(item)
    return {
        "item_id": item_id,
        "backlog_status": item.get("status", "new"),
        "metric": metric,
        "preview_markdown": render_preview_markdown(item, metric),
    }


def apply_metric_overrides(
    metric: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    result = dict(metric)
    for key in (
        "metric_key",
        "display_name_th",
        "business_definition_th",
        "playbook_th",
        "example_questions_th",
    ):
        value = overrides.get(key)
        if value is not None:
            result[key] = value
    return result


async def approve_promotion(
    item_id: str,
    *,
    approved: bool,
    overrides: dict[str, Any] | None = None,
    approved_by: str = "data_engineer",
) -> dict[str, Any]:
    if not approved:
        return {"item_id": item_id, "status": "cancelled", "metric": None}

    preview = get_promotion_preview(item_id)
    metric = apply_metric_overrides(preview["metric"], overrides or {})
    metric["approved_at"] = datetime.now(timezone.utc).isoformat()
    metric["approved_by"] = approved_by

    await promote_metric(metric)
    backlog_store.update_item(item_id, {"status": "promoted"})

    return {"item_id": item_id, "status": "promoted", "metric": metric}
