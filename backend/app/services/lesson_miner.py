"""Mine data/local/logs/pdca_failures.jsonl into short DA-prompt lessons (Phase J).

Deterministic and templated on purpose (evidence-first principle, roadmap
§2 #1) — a lesson is a frequency-clustered fact about past failures, never
an LLM's guess about what might help.

No automatic scheduling in this phase (see Phase J phase doc Deviation
Log — adding a job kind needs owner sign-off first); trigger manually via
``scripts/mine_lessons.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.local_paths import get_local_dir
from backend.app.services.sql_error_classifier import classify_sql_error

TOP_N_DEFAULT = 10

_LESSON_TEMPLATES = {
    "row_count": "ผลลัพธ์เกินขนาดที่กำหนดบ่อย ({n} ครั้ง) — เพิ่ม WHERE filter (ช่วงเวลา/หน่วยงาน/ประเภทเอกสาร) ก่อนเสมอ อย่าใช้ SELECT * แบบไม่จำกัดขอบเขต",
    "invalid_column": "ชื่อคอลัมน์ผิดบ่อย ({n} ครั้ง) — ตรวจสอบชื่อคอลัมน์ให้ตรงกับ Schema Context Pack ก่อนเขียน SQL อย่าเดาชื่อคอลัมน์",
    "timeout": "Query timeout บ่อย ({n} ครั้ง) — ลดขอบเขตข้อมูล (แคบช่วงเวลา/เพิ่ม filter) แทนการ query ตารางเต็ม",
    "connection": "เชื่อมต่อฐานข้อมูลล้มเหลวบ่อย ({n} ครั้ง) — มักเป็นปัญหาเครือข่าย/สิทธิ์ ไม่ใช่ตัว SQL เอง ตรวจสถานะ Fabric/Postgres ก่อน retry",
    "generic": "ข้อผิดพลาดทั่วไปที่พบบ่อย ({n} ครั้ง) — ตรวจ syntax ให้ตรงกับ dialect (T-SQL vs PostgreSQL) ที่ใช้งานอยู่ขณะนั้น",
}


def _pdca_path() -> Path:
    return get_local_dir() / "logs" / "pdca_failures.jsonl"


def _lessons_path() -> Path:
    path = get_local_dir() / "knowledge"
    path.mkdir(parents=True, exist_ok=True)
    return path / "sql_lessons.json"


def _read_failures(jsonl_path: Path) -> list[dict[str, Any]]:
    if not jsonl_path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def mine_lessons(
    *, jsonl_path: Path | None = None, top_n: int = TOP_N_DEFAULT
) -> list[dict[str, Any]]:
    """Cluster PDCA SQL failures by error class into top-N short lessons."""
    failures = _read_failures(jsonl_path or _pdca_path())
    if not failures:
        return []

    buckets: dict[str, list[dict[str, Any]]] = {}
    for f in failures:
        klass = classify_sql_error(f.get("error") or "")
        buckets.setdefault(klass, []).append(f)

    lessons = []
    for klass, items in buckets.items():
        template = _LESSON_TEMPLATES.get(klass, _LESSON_TEMPLATES["generic"])
        lessons.append(
            {
                "error_class": klass,
                "count": len(items),
                "lesson_th": template.format(n=len(items)),
                "example_error": (items[-1].get("error") or "")[:300],
                "last_seen": items[-1].get("at") or items[-1].get("timestamp"),
            }
        )
    lessons.sort(key=lambda entry: entry["count"], reverse=True)
    return lessons[:top_n]


def write_lessons(lessons: list[dict[str, Any]], *, path: Path | None = None) -> Path:
    out_path = path or _lessons_path()
    payload = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lessons": lessons,
    }
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out_path)
    return out_path


def load_lessons(*, path: Path | None = None) -> list[dict[str, Any]]:
    lessons_path = path or _lessons_path()
    if not lessons_path.exists():
        return []
    data = json.loads(lessons_path.read_text(encoding="utf-8"))
    return data.get("lessons") or []


def format_lessons_context(*, path: Path | None = None) -> str:
    lessons = load_lessons(path=path)
    if not lessons:
        return ""
    lines = ["## Known SQL lessons (avoid repeating past mistakes)"]
    for lesson in lessons:
        lines.append(f"- [{lesson['error_class']}] {lesson['lesson_th']}")
    return "\n".join(lines)


def run_lesson_mining(
    *,
    jsonl_path: Path | None = None,
    output_path: Path | None = None,
    top_n: int = TOP_N_DEFAULT,
) -> dict[str, Any]:
    """Mine + write in one call — used by scripts/mine_lessons.py."""
    failures = _read_failures(jsonl_path or _pdca_path())
    lessons = mine_lessons(jsonl_path=jsonl_path, top_n=top_n)
    out_path = write_lessons(lessons, path=output_path)
    return {
        "total_failures": len(failures),
        "lessons_written": len(lessons),
        "output_path": str(out_path),
    }
