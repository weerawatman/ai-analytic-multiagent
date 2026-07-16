"""Generate and store multi-role insight briefs after discovery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.discovery_service import format_schema_context_pack, load_discovery
from backend.app.services.knowledge_store import format_knowledge_context
from backend.app.services.local_paths import get_local_dir

ROLE_PROMPTS = {
    "data_engineer": """จาก discovery context ด้านล่าง สร้าง 2-3 insight briefs มุม Data Engineer
คืน JSON array: [{{"title_th":"...","summary_th":"...","priority":"high|medium|low"}}]
Context:
{context}""",
    "data_analyst": """จาก discovery context สร้าง 2-3 briefs มุม Data Analyst (metrics/SQL ที่วัดได้)
คืน JSON array เท่านั้น
Context:
{context}""",
    "data_scientist": """จาก discovery context สร้าง 2-3 briefs มุม Data Scientist (sanity/anomaly)
คืน JSON array เท่านั้น
Context:
{context}""",
    "business_analyst": """จาก discovery context สร้าง 2-3 briefs มุม Business Analyst (นิยามธุรกิจ/KPI)
คืน JSON array เท่านั้น
Context:
{context}""",
}


def _briefing_path(theme_id: str) -> Path:
    path = get_local_dir() / "briefings"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{theme_id}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _heuristic_briefs(role: str, discovery: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = discovery.get("profiles", [])
    table_names = [p.get("table", "") for p in profiles[:3]]
    tables_str = ", ".join(table_names) if table_names else "warehouse"
    templates = {
        "data_engineer": [
            {
                "title_th": f"โครงสร้างข้อมูล {tables_str}",
                "summary_th": f"พบ {len(profiles)} ตาราง — ควรตรวจ grain และ key ก่อนวิเคราะห์",
                "priority": "high",
            },
        ],
        "data_analyst": [
            {
                "title_th": "Metric ที่วัดได้จากข้อมูล",
                "summary_th": "แนะนำเริ่มจากตารางที่มี date column และ measure columns",
                "priority": "medium",
            },
        ],
        "data_scientist": [
            {
                "title_th": "มุม sanity check",
                "summary_th": "เปรียบเทียบ row count และ sample ก่อนสรุป insight",
                "priority": "medium",
            },
        ],
        "business_analyst": [
            {
                "title_th": "นิยามธุรกิจที่ต้อง validate",
                "summary_th": "CEO ควรยืนยันนิยาม metric หลักก่อนใช้ในรายงาน",
                "priority": "high",
            },
        ],
    }
    return templates.get(role, [])


async def _generate_role_briefs(role: str, context: str) -> list[dict[str, Any]]:
    llm = make_chat_ollama(temperature=0.2)
    prompt = ROLE_PROMPTS[role].format(context=context[:4000])
    try:
        response = await llm.ainvoke(prompt)
        import re
        content = str(response.content)
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            briefs: list[dict[str, Any]] = json.loads(match.group())
            for b in briefs:
                b["id"] = str(uuid4())
                b["role"] = role
                b["status"] = "pending"
            return briefs
    except Exception as exc:
        logger.warning("LLM briefing failed for %s: %s", role, exc)
    return []


async def generate_briefings(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    discovery = load_discovery(theme_id)
    if not discovery:
        raise ValueError(f"No discovery data for theme {theme_id} — run discovery first")

    schema_ctx = format_schema_context_pack(theme_id)
    knowledge_ctx = format_knowledge_context(theme=theme_name or theme_id)
    context = f"{schema_ctx}\n\n{knowledge_ctx}"

    all_briefs: list[dict[str, Any]] = []
    for role in ("data_engineer", "data_analyst", "data_scientist", "business_analyst"):
        briefs = await _generate_role_briefs(role, context)
        if not briefs:
            briefs = _heuristic_briefs(role, discovery)
            for b in briefs:
                b["id"] = str(uuid4())
                b["role"] = role
                b["status"] = "pending"
        all_briefs.extend(briefs)

    payload = {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "generated_at": _utc_now(),
        "briefs": all_briefs,
    }
    path = _briefing_path(theme_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return payload


def load_briefings(theme_id: str) -> dict[str, Any] | None:
    path = _briefing_path(theme_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
