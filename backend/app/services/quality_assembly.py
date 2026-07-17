"""Assemble Explore responses to Quality Bar D standard."""

from __future__ import annotations

import re
from typing import Any

from backend.app.agents.state import AgentState
from backend.app.services import backlog_store
from backend.app.services.fabric_sql import (
    OFFLINE_SQL_MSG_TH,
    RowCountExceeded,
    enforce_row_count_threshold_for_source,
    fabric_can_query,
    format_query_preview,
    pg_can_query,
    run_sql,
)

SQL_FAILED_CEO_MSG_TH = (
    "ทีม Data Analyst ลองปรับ SQL แล้ว 3 ครั้งแต่ยังไม่สำเร็จ "
    "กรุณาปรับคำถามให้เจาะจงขึ้น เช่น ระบุช่วงเวลา หรือหน่วยงานที่สนใจ"
)

# Provenance labels (Phase F) — the CEO must always see which source produced
# the numbers, especially on the Postgres fallback where sync freshness is not
# yet confirmed (D-2.3). Never fall back silently.
DATA_SOURCE_LABEL_TH = {
    "fabric": "Microsoft Fabric DW (แหล่งข้อมูลหลัก)",
    "postgres": (
        "Postgres mirror (ฐานข้อมูลสำรอง — Fabric ไม่พร้อมขณะรัน "
        "ข้อมูลชุดเดียวกันแต่รอบ sync ล่าสุดอาจช้ากว่า Fabric)"
    ),
    "offline": "Offline — ไม่ได้รัน SQL จริง (draft จาก discovery บนดิสก์เท่านั้น)",
}


def data_source_label_th(source: str) -> str:
    return DATA_SOURCE_LABEL_TH.get(source or "", DATA_SOURCE_LABEL_TH["offline"])


def _current_sql_source() -> str:
    """Same resolution as data_analyst._current_sql_source — kept local so
    tests that monkeypatch this module's `fabric_can_query` keep working."""
    if fabric_can_query():
        return "fabric"
    if pg_can_query():
        return "postgres"
    return "offline"


def _run_sample_sql(sql: str, mode: str, source: str) -> dict[str, Any]:
    """Sample-row query with the same pre-flight row-count guard as the DA path.

    `source` must match the dialect `sql` was written in — pass
    `state.sql_source` (the connector that actually ran this SQL) rather than
    re-resolving fresh, since reachability may have changed since DA ran.

    Without the guard a fail-open in D1 would let quality assembly re-scan an
    oversized result here (DE review, Phase D). RowCountExceeded propagates to
    the caller, which renders a short note instead of sample rows.
    """
    enforce_row_count_threshold_for_source(sql, source)
    return run_sql(sql, mode=mode, max_rows=5, source=source)


def _extract_section(text: str, tag: str) -> str:
    pattern = rf"{tag}:\s*(.*?)(?=\n[A-Z_]+:|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_list_section(text: str, tag: str) -> list[str]:
    raw = _extract_section(text, tag)
    if not raw:
        return []
    return [line.strip("- •\t ").strip() for line in raw.splitlines() if line.strip()]


def _extract_sql_from_text(text: str) -> str:
    match = re.search(r"```sql\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if "SQL:" in text:
        part = text.split("SQL:")[-1]
        for marker in ("ANALYSIS:", "ALT_SQL:", "ASSUMPTIONS:"):
            if marker in part:
                part = part.split(marker)[0]
        return part.strip()
    return ""


def build_quality_payload(state: AgentState) -> dict[str, Any]:
    """Build structured insight candidate from agent state."""
    combined = "\n".join(
        filter(
            None,
            [state.query_result, state.analysis_summary, state.schema_info, state.ba_summary],
        )
    )

    sql_primary = state.generated_sql or _extract_sql_from_text(combined)
    sql_alternative = _extract_section(combined, "ALT_SQL") or _extract_sql_from_text(
        state.analysis_summary
    )

    assumptions = _parse_list_section(combined, "ASSUMPTIONS")
    if not assumptions:
        assumptions = _parse_list_section(state.analysis_summary, "ASSUMPTIONS")
    if not assumptions:
        assumptions = ["grain และ filter ยังไม่ได้ validate กับ BA/DA"]

    unknowns = _parse_list_section(combined, "UNKNOWNS") or _parse_list_section(
        state.analysis_summary, "UNKNOWNS"
    )
    if not unknowns:
        unknowns = ["ยังไม่ได้ยืนยันวิธีคำนวณกับทีม BA/DA"]

    questions = _parse_list_section(combined, "QUESTIONS_FOR_BA_DA") or _parse_list_section(
        state.analysis_summary, "QUESTIONS_FOR_BA_DA"
    )
    if not questions:
        questions = [
            "นิยาม metric นี้ตรงกับรายงานเดิมหรือไม่?",
            "ควรใช้ filter อะไรเป็นมาตรฐาน?",
        ]

    confidence = _extract_section(combined, "CONFIDENCE").lower() or "medium"
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    # Prefer the source that actually ran generated_sql — the SQL text matches
    # that connector's dialect. Only re-resolve fresh when DA never set it.
    source = getattr(state, "sql_source", "") or _current_sql_source()

    sample_preview = ""
    sample_ref = ""
    sql_failed = bool(getattr(state, "sql_failed", False))
    if sql_failed:
        sample_preview = "(ข้ามตัวอย่างข้อมูล — SQL ยังรันไม่สำเร็จหลังลองปรับแล้ว)"
        sample_ref = "skipped_sql_failed"
    elif sql_primary:
        if source == "offline":
            sample_preview = f"({OFFLINE_SQL_MSG_TH})"
            sample_ref = "skipped_offline"
        else:
            try:
                primary_result = _run_sample_sql(sql_primary, state.mode or "explore", source)
                sample_preview = format_query_preview(primary_result)
                sample_ref = "inline"
            except RowCountExceeded as exc:
                sample_preview = f"(ข้ามตัวอย่างข้อมูล — {exc.message_th})"
                sample_ref = "skipped_row_count"
            except Exception as exc:
                # Keep message short — never dump a full traceback into the CEO report.
                sample_preview = f"(รัน SQL ไม่สำเร็จ: {type(exc).__name__})"

    if (
        not sql_failed
        and sql_alternative
        and sql_alternative != sql_primary
        and source != "offline"
    ):
        try:
            alt_result = _run_sample_sql(sql_alternative, state.mode or "explore", source)
            sample_preview += "\n\n--- Sanity check ---\n" + format_query_preview(alt_result)
        except Exception:
            pass
    elif (
        not sql_failed
        and sql_alternative
        and sql_alternative != sql_primary
        and source == "offline"
    ):
        sample_preview += f"\n\n--- Sanity check ---\n({OFFLINE_SQL_MSG_TH})"

    last_question = ""
    for m in reversed(state.messages):
        if getattr(m, "type", "") == "human":
            last_question = m.content
            break

    answer_summary = (
        _extract_section(combined, "ANALYSIS")
        or _extract_section(state.ba_summary, "BUSINESS_SUMMARY")
        or state.final_answer
        or combined[:500]
    )

    scientist_critique = (
        _extract_section(state.analysis_summary, "CRITIQUE")
        or state.analysis_summary[:2000]
        if state.analysis_summary
        else ""
    )

    if sql_failed:
        answer_summary = SQL_FAILED_CEO_MSG_TH
        confidence = "low"
        if SQL_FAILED_CEO_MSG_TH not in unknowns:
            unknowns = [SQL_FAILED_CEO_MSG_TH, *unknowns]
    elif "SQL_ERROR:" in answer_summary or "Traceback" in answer_summary:
        # Never leak raw exception strings into the CEO-facing summary.
        answer_summary = answer_summary.split("SQL_ERROR:")[0].strip()[:500] or SQL_FAILED_CEO_MSG_TH

    payload = {
        "theme": state.theme or "",
        "mode": state.mode or "explore",
        "question_th": last_question,
        "answer_summary_th": answer_summary[:2000],
        "ba_summary_th": (state.ba_summary or "")[:2000],
        "scientist_critique_th": scientist_critique[:2000],
        "de_context_th": (state.schema_info or "")[:1500],
        "agents_involved": [
            r
            for r, val in (
                ("data_engineer", state.schema_info),
                ("data_analyst", state.query_result),
                ("data_scientist", state.analysis_summary),
                ("business_analyst", state.ba_summary),
            )
            if val
        ],
        "sql_primary": sql_primary,
        "sql_alternative": sql_alternative,
        "assumptions": assumptions,
        "confidence": confidence,
        "unknowns": unknowns,
        "questions_for_ba_da": questions,
        "sample_data_ref": sample_ref,
        "sample_preview": sample_preview,
        "data_source": source,
        "sql_failed": sql_failed,
        "sql_retry_count": int(getattr(state, "sql_retry_count", 0) or 0),
        "sql_error": getattr(state, "sql_error", "") or "",
        "status": "new",
    }
    return payload


def format_explore_response_th(payload: dict[str, Any]) -> str:
    """Render Thai markdown report for UI."""
    lines = [
        "🟡 **Draft · Explore** — รอ validate กับ BA/DA",
        "",
    ]
    source = payload.get("data_source", "")
    if source:
        icon = {"fabric": "🟦", "postgres": "🟨", "offline": "⚪"}.get(source, "⚪")
        lines += [f"{icon} **แหล่งข้อมูล:** {data_source_label_th(source)}", ""]
    if payload.get("sql_failed"):
        lines += [
            "### สถานะ SQL",
            f"⚠️ {SQL_FAILED_CEO_MSG_TH}",
            "",
        ]
    lines += [
        "### สรุป",
        payload.get("answer_summary_th") or "-",
        "",
        "### SQL หลัก",
        f"```sql\n{payload.get('sql_primary') or '-- ไม่มี SQL'}\n```",
    ]
    if payload.get("sql_alternative"):
        lines += ["", "### SQL ทางเลือก / Sanity check", f"```sql\n{payload['sql_alternative']}\n```"]
    lines += [
        "",
        "### Assumptions",
        *[f"- {a}" for a in payload.get("assumptions", [])],
        "",
        f"**Confidence:** {payload.get('confidence', 'medium')}",
        "",
        "### สิ่งที่ยังไม่รู้",
        *[f"- {u}" for u in payload.get("unknowns", [])],
        "",
        "### คำถามที่ควรถาม BA/DA",
        *[f"- {q}" for q in payload.get("questions_for_ba_da", [])],
    ]
    if payload.get("scientist_critique_th"):
        lines += [
            "",
            "### มุม Data Scientist (DS — sanity & critique)",
            payload["scientist_critique_th"],
        ]
    if payload.get("ba_summary_th"):
        lines += ["", "### มุม Business Analyst (BA)", payload["ba_summary_th"]]
    if payload.get("sample_preview"):
        lines += ["", "### ตัวอย่างข้อมูล", f"```json\n{payload['sample_preview']}\n```"]
    return "\n".join(lines)


def validate_quality_bar_d(payload: dict[str, Any]) -> list[str]:
    """Return list of missing requirements for Quality Bar D."""
    missing: list[str] = []
    if not payload.get("sql_primary"):
        missing.append("sql_primary")
    if not payload.get("assumptions"):
        missing.append("assumptions")
    if not payload.get("questions_for_ba_da"):
        missing.append("questions_for_ba_da")
    if not payload.get("answer_summary_th"):
        missing.append("answer_summary_th")
    if not payload.get("sql_alternative") and not payload.get("sample_preview"):
        missing.append("sanity_check_or_sample")
    return missing


def save_quality_to_backlog(payload: dict[str, Any]) -> dict[str, Any]:
    missing = validate_quality_bar_d(payload)
    if missing:
        raise ValueError(f"Quality Bar D incomplete: {', '.join(missing)}")
    store_payload = {
        k: v
        for k, v in payload.items()
        if k not in ("sample_preview", "quality_gaps")
    }
    return backlog_store.create_item(store_payload)
