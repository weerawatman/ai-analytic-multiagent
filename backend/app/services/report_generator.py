"""Generate Thai Markdown handoff reports for BA/DA."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.local_paths import get_local_dir


def _exports_dir() -> Path:
    path = get_local_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_handoff_markdown(item: dict[str, Any]) -> str:
    """Build Thai Markdown report from backlog item."""
    lines = [
        f"# รายงาน Insight Candidate — {item.get('question_th', 'ไม่ระบุคำถาม')}",
        "",
        f"**สถานะ:** {item.get('status', 'new')}  ",
        f"**Theme:** {item.get('theme') or '-'}  ",
        f"**โหมด:** {item.get('mode', 'explore')}  ",
        f"**Confidence:** {item.get('confidence', 'medium')}  ",
        f"**สร้างเมื่อ:** {item.get('created_at', '-')}  ",
        f"**อัปเดตล่าสุด:** {item.get('updated_at', '-')}  ",
        "",
        "> 🟡 เอกสารนี้เป็น Draft จากโหมด Explore — ใช้สำหรับคุย validate กับ BA/DA",
        "",
        "## สรุป Insight",
        item.get("answer_summary_th") or "-",
        "",
        "## SQL หลัก",
        "```sql",
        item.get("sql_primary") or "-- ไม่มี SQL",
        "```",
    ]

    if item.get("sql_alternative"):
        lines += [
            "",
            "## SQL ทางเลือก / Sanity Check",
            "```sql",
            item["sql_alternative"],
            "```",
        ]

    assumptions = item.get("assumptions") or []
    unknowns = item.get("unknowns") or []
    questions = item.get("questions_for_ba_da") or []

    lines += ["", "## Assumptions"]
    lines += [f"- {a}" for a in assumptions] if assumptions else ["- (ไม่ระบุ)"]
    lines += ["", "## สิ่งที่ยังไม่รู้"]
    lines += [f"- {u}" for u in unknowns] if unknowns else ["- (ไม่ระบุ)"]
    lines += ["", "## คำถามที่ควรถาม BA/DA"]
    lines += [f"- {q}" for q in questions] if questions else ["- (ไม่ระบุ)"]

    feedback = item.get("ba_da_feedback") or []
    lines += ["", "## Feedback จาก BA/DA"]
    if feedback:
        for fb in feedback:
            lines.append(f"- **{fb.get('at', '-')}:** {fb.get('note', '')}")
    else:
        lines.append("- (ยังไม่มี feedback — กรอกหลังคุยทีม)")

    lines += [
        "",
        "## ช่องบันทึกหลัง Meeting",
        "| หัวข้อ | คำตอบจาก BA/DA |",
        "|--------|----------------|",
        "| นิยาม metric ที่ถูกต้อง | |",
        "| วิธีคำนวณมาตรฐาน | |",
        "| ข้อยกเว้น / edge cases | |",
        "| ผู้ validate | |",
        "| วันที่ validate | |",
        "",
        "---",
        f"*Generated at {datetime.now(timezone.utc).isoformat()}*",
    ]
    return "\n".join(lines)


def export_backlog_item(item: dict[str, Any]) -> dict[str, str]:
    """Write Markdown report to data/local/exports/ and return metadata."""
    content = render_handoff_markdown(item)
    item_id = item["id"]
    filename = f"{item_id}.md"
    path = _exports_dir() / filename
    path.write_text(content, encoding="utf-8")
    return {
        "item_id": item_id,
        "file_path": str(path),
        "filename": filename,
        "content": content,
    }
