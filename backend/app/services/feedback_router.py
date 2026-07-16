"""Route CEO feedback to role-owned knowledge stores and team memory."""

from __future__ import annotations

import re
from typing import Any

from backend.app.core.logger import logger
from backend.app.services import knowledge_store
from backend.app.services.team_memory_store import append_role_feedback_note


async def apply_feedback(
    theme_id: str,
    *,
    role: str,
    action: str,
    comment: str,
    brief_id: str = "",
    theme_name: str = "",
) -> dict[str, Any]:
    """Apply CEO feedback to the store each role owns."""
    append_role_feedback_note(
        theme_id,
        role,
        action=action,
        comment=comment,
        brief_id=brief_id,
    )

    applied: list[str] = []
    if not comment.strip():
        return {"applied": applied, "message": "Feedback logged (no comment to route)"}

    theme = theme_name or theme_id
    text = comment.strip()

    if role == "data_engineer":
        applied.extend(await _apply_de_feedback(theme, text, action))
    elif role == "data_analyst":
        applied.extend(await _apply_da_feedback(theme, text, action))
    elif role == "business_analyst":
        applied.extend(await _apply_ba_feedback(theme, text, action))
    elif role == "data_scientist":
        applied.append("team_memory:data_scientist feedback note")

    logger.info("Feedback routed theme=%s role=%s applied=%s", theme_id, role, applied)
    return {"applied": applied, "message": f"Routed {len(applied)} update(s) for {role}"}


async def _apply_de_feedback(theme: str, comment: str, action: str) -> list[str]:
    applied: list[str] = []
    join_match = re.search(
        r"(\S+\.\S+)\s*(?:join|->|→)\s*(\S+\.\S+)\s*(?:on|ON)\s*(.+)",
        comment,
        re.I,
    )
    if join_match:
        await knowledge_store.add_item(
            "relationships",
            {
                "from_table": join_match.group(1),
                "to_table": join_match.group(2),
                "join_keys": join_match.group(3).strip(),
                "theme": theme,
                "status": "draft" if action != "approve" else "approved",
            },
        )
        applied.append("relationships:join")
        return applied

    if "join" in comment.lower() or "relationship" in comment.lower():
        await knowledge_store.add_item(
            "relationships",
            {
                "from_table": "",
                "to_table": "",
                "join_keys": comment[:200],
                "theme": theme,
                "status": "draft",
            },
        )
        applied.append("relationships:note")
    return applied


async def _apply_da_feedback(theme: str, comment: str, action: str) -> list[str]:
    applied: list[str] = []
    field_match = re.search(
        r"([\w.]+\.\w+)\s*[=:]\s*(.+)|(?:column|คอลัมน์|ฟิลด์)\s*[`']?(\w+)[`']?",
        comment,
        re.I,
    )
    if field_match:
        field_key = field_match.group(1) or field_match.group(3) or "metric.custom"
        definition = field_match.group(2) or comment
        await knowledge_store.add_item(
            "glossary",
            {
                "field_key": field_key,
                "definition_th": definition.strip(),
                "theme": theme,
                "status": "approved" if action == "approve" else "draft",
            },
        )
        applied.append(f"glossary:{field_key}")
        return applied

    if any(kw in comment for kw in ("ยอดขาย", "metric", "นิยาม", "SUM", "column")):
        await knowledge_store.add_item(
            "glossary",
            {
                "field_key": "metric.feedback",
                "definition_th": comment[:500],
                "theme": theme,
                "status": "approved" if action == "approve" else "draft",
            },
        )
        applied.append("glossary:metric.feedback")
    return applied


async def _apply_ba_feedback(theme: str, comment: str, action: str) -> list[str]:
    applied: list[str] = []
    if len(comment) >= 5:
        await knowledge_store.add_item(
            "targets",
            {
                "name_th": comment[:120],
                "description_th": comment,
                "theme": theme,
                "status": "approved" if action == "approve" else "draft",
            },
        )
        applied.append("targets:ceo_feedback")
    return applied
