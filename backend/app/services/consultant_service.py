"""Claude external consultant — advice only; never replaces the local AI team."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.agents.skill_loader import load_agent_skill
from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services.consultant_redaction import (
    build_consultant_sections,
    sections_to_payload_text,
)
from backend.app.services.local_paths import get_local_dir
from backend.app.services import knowledge_store
from backend.app.services.team_memory_store import (
    append_consultant_note,
    append_role_feedback_note,
)

_client: Any = None

COACH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["role_coaching", "glossary_proposals", "relationship_proposals"],
    "properties": {
        "role_coaching": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "data_engineer",
                "data_analyst",
                "data_scientist",
                "business_analyst",
            ],
            "properties": {
                "data_engineer": {"type": "string"},
                "data_analyst": {"type": "string"},
                "data_scientist": {"type": "string"},
                "business_analyst": {"type": "string"},
            },
        },
        "glossary_proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field_key", "definition_th"],
                "properties": {
                    "field_key": {"type": "string"},
                    "definition_th": {"type": "string"},
                },
            },
        },
        "relationship_proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["from_table", "to_table", "join_keys"],
                "properties": {
                    "from_table": {"type": "string"},
                    "to_table": {"type": "string"},
                    "join_keys": {"type": "string"},
                },
            },
        },
    },
}

_MODE_TOGGLES = {
    "review_chat": "consultant_review_chat",
    "coach_onboarding": "consultant_coach_onboarding",
    "on_demand": "consultant_on_demand",
    "help_when_stuck": "consultant_help_when_stuck",
}


def _get_client() -> Any:
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic

        settings = get_settings()
        _client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.consultant_timeout,
            max_retries=1,
        )
    return _client


def is_enabled(mode: str) -> bool:
    settings = get_settings()
    if not settings.consultant_is_enabled:
        return False
    attr = _MODE_TOGGLES.get(mode)
    if not attr:
        return False
    return bool(getattr(settings, attr, False))


def _audit_path() -> Path:
    path = get_local_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path / "consultant_audit.jsonl"


def _append_audit(record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    path = _audit_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


async def _audit(record: dict[str, Any]) -> None:
    await asyncio.to_thread(_append_audit, record)


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(block.text)
    return "\n".join(parts).strip()


async def _call_claude(
    mode: str,
    theme_id: str,
    payload_text: str,
    *,
    user_instruction: str,
    output_schema: dict[str, Any] | None = None,
) -> str | None:
    settings = get_settings()
    skill = load_agent_skill("consultant")
    payload_sha = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    base_audit = {
        "at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "theme_id": theme_id,
        "model": settings.consultant_model,
        "payload_chars": len(payload_text),
        "payload_sha256": payload_sha,
        "payload": payload_text,
    }

    if not settings.consultant_is_enabled:
        await _audit({**base_audit, "status": "error", "error": "consultant disabled", "response_chars": 0, "usage": None})
        return None

    try:
        client = _get_client()
        kwargs: dict[str, Any] = {
            "model": settings.consultant_model,
            "max_tokens": settings.consultant_max_tokens,
            "thinking": {"type": "adaptive"},
            "system": skill,
            "messages": [
                {
                    "role": "user",
                    "content": f"{user_instruction}\n\n---\n{payload_text}",
                }
            ],
        }
        if output_schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": output_schema}
            }

        response = await client.messages.create(**kwargs)
        text = _extract_text(response)
        usage = getattr(response, "usage", None)
        await _audit(
            {
                **base_audit,
                "status": "ok",
                "error": None,
                "response_chars": len(text),
                "usage": {
                    "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                    "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
                },
            }
        )
        return text or None
    except Exception as exc:
        logger.exception("Consultant Claude call failed mode=%s", mode)
        await _audit(
            {
                **base_audit,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "response_chars": 0,
                "usage": None,
            }
        )
        return None


def _is_stuck(state: Any) -> bool:
    errors = getattr(state, "step_errors", None) or []
    if errors:
        return True
    qp = getattr(state, "quality_payload", None) or {}
    gaps = qp.get("quality_gaps") or []
    return bool(gaps)


def should_review(state: Any) -> bool:
    if is_enabled("review_chat"):
        return True
    return is_enabled("help_when_stuck") and _is_stuck(state)


async def review_answer(
    theme_id: str,
    theme: str,
    question: str,
    draft_answer: str,
    quality_payload: dict[str, Any],
    step_errors: list[str] | None,
) -> str | None:
    """Modes 1+4: review draft answer; add TROUBLESHOOTING when stuck."""
    stuck = bool(step_errors) or bool((quality_payload or {}).get("quality_gaps"))
    sections = build_consultant_sections(
        theme_id=theme_id,
        theme=theme,
        question=question,
        draft_answer=draft_answer,
        ba_summary=str((quality_payload or {}).get("ba_summary") or ""),
        ds_critique=str((quality_payload or {}).get("ds_critique") or ""),
        quality_payload=quality_payload,
        step_errors=step_errors,
        include_troubleshooting=stuck and is_enabled("help_when_stuck"),
    )
    payload = sections_to_payload_text(sections)
    instruction = (
        "โหมด: review — รีวิวคำตอบ draft ของทีม Local ก่อนส่ง CEO "
        "ตามรูปแบบ review ใน SKILL"
    )
    return await _call_claude("review", theme_id, payload, user_instruction=instruction)


async def coach_team(theme_id: str, theme_name: str) -> dict[str, Any] | None:
    """Mode 2 — structured coaching after onboarding."""
    if not is_enabled("coach_onboarding"):
        return None

    sections = build_consultant_sections(
        theme_id=theme_id,
        theme=theme_name or theme_id,
        question="โค้ชทีมหลัง onboarding — เสนอวิธีพัฒนาแต่ละตำแหน่งและ knowledge drafts",
    )
    payload = sections_to_payload_text(sections)
    text = await _call_claude(
        "coach",
        theme_id,
        payload,
        user_instruction="โหมด: coach — ตอบเป็น JSON ตาม schema เท่านั้น",
        output_schema=COACH_SCHEMA,
    )
    if not text:
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Consultant coach returned non-JSON")
        return None

    coaching = data.get("role_coaching") or {}
    for role, note in coaching.items():
        if note and str(note).strip():
            append_role_feedback_note(
                theme_id,
                role,
                action="consultant_coach",
                comment=f"[ที่ปรึกษา] {note}",
            )

    theme = theme_name or theme_id
    for prop in data.get("glossary_proposals") or []:
        if not prop.get("field_key"):
            continue
        await knowledge_store.upsert_item(
            "glossary",
            {
                "field_key": prop["field_key"],
                "definition_th": prop.get("definition_th") or "",
                "theme": theme,
                "status": "draft",
                "source": "consultant",
            },
        )

    for prop in data.get("relationship_proposals") or []:
        await knowledge_store.upsert_item(
            "relationships",
            {
                "from_table": prop.get("from_table") or "",
                "to_table": prop.get("to_table") or "",
                "join_keys": prop.get("join_keys") or "",
                "theme": theme,
                "status": "draft",
                "source": "consultant",
            },
        )

    return data


async def answer_question(theme_id: str, question: str) -> str | None:
    """Mode 3 — on-demand consult."""
    if not is_enabled("on_demand"):
        return None

    sections = build_consultant_sections(
        theme_id=theme_id,
        theme=theme_id,
        question=question,
    )
    payload = sections_to_payload_text(sections)
    advice = await _call_claude(
        "consult",
        theme_id,
        payload,
        user_instruction="โหมด: consult — ตอบคำถามของ CEO/เจ้าของระบบโดยตรง",
    )
    if advice:
        append_consultant_note(theme_id, advice)
    return advice


# Re-export for tests that may patch _get_client
__all__ = [
    "is_enabled",
    "should_review",
    "review_answer",
    "coach_team",
    "answer_question",
    "_get_client",
    "COACH_SCHEMA",
]
