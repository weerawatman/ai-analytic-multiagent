"""Deterministic data-homework profiling for a theme — no LLM involved.

Produces a persisted evidence artifact (``homework.json`` next to the theme's
``discovery.json``) that proves the team did real profiling work:

- source/provenance + freshness timestamp + evidence level
- table roles (fact / dimension / unknown / empty)
- row counts and date ranges (bounded single-row aggregates)
- column null/cardinality summaries from bounded samples (TOP/LIMIT)
- verified metric definitions available for the theme
- candidate joins with confidence + needs-confirmation flags
- data-quality issues (empty tables, high nulls, varchar-typed measures)
- role-specific homework (DE schema/quality, DS hypotheses/statistical
  checks, DA baseline SQL, BA business questions)

All live reads go through the existing read-only SQL guard and connectors,
are strictly bounded (sample rows, single-row aggregates, wall-clock budget)
and fail soft: any per-query error degrades the evidence level instead of
crashing the caller. This is deterministic profiling + hypothesis generation,
NOT machine learning — and it is labeled as such.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger
from backend.app.services.discovery_service import load_discovery
from backend.app.services.fabric_sql import get_active_sql_source, run_sql
from backend.app.services.knowledge_store import _path_for, _visible_to_prompts
from backend.app.services.local_paths import get_local_dir

_MAX_FOCUS_TABLES = 3
_SAMPLE_ROWS = 200
_MAX_STAT_COLUMNS = 24
_LIVE_BUDGET_SECONDS = 240

EVIDENCE_LEVELS = {
    "fabric": "fabric_live",
    "postgres": "postgres_live",
    "offline": "disk_cache",
}

_DATE_HINTS = ("sourcemonth", "date", "fiscal_year", "period")
_MEASURE_HINTS = ("revenue", "cogs", "margin", "amount", "value", "qty", "quantity", "inter_company")
_KEY_HINTS = ("profit_center", "plant", "material", "customer", "company", "document", "_id", "center")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _homework_path(theme_id: str) -> Path:
    path = get_local_dir() / "knowledge" / "themes" / theme_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "homework.json"


def load_homework(theme_id: str) -> dict[str, Any] | None:
    path = _homework_path(theme_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_homework(theme_id: str, data: dict[str, Any]) -> dict[str, Any]:
    path = _homework_path(theme_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)
    return data


def classify_table_role(profile: dict[str, Any]) -> str:
    """Heuristic fact/dimension classification from discovery metadata."""
    name = str(profile.get("table_name") or profile.get("table") or "").lower()
    row_count = profile.get("row_count")
    if row_count == 0:
        return "empty"
    if name.startswith("dim_"):
        return "dimension"
    if isinstance(row_count, int) and row_count >= 100_000:
        return "fact"
    if isinstance(row_count, int) and row_count < 100_000:
        return "dimension"
    return "unknown"


def _pick_focus_tables(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts = [p for p in profiles if classify_table_role(p) == "fact"]
    facts.sort(key=lambda p: p.get("row_count") or 0, reverse=True)
    return facts[:_MAX_FOCUS_TABLES]


def _interesting_columns(profile: dict[str, Any]) -> list[str]:
    """Date columns + measures + keys, capped — order preserved for stability."""
    cols = [str(c.get("COLUMN_NAME", "")) for c in profile.get("columns", [])]
    picked: list[str] = []

    def _match(hints: tuple[str, ...]) -> None:
        for col in cols:
            low = col.lower()
            if col not in picked and any(h in low for h in hints):
                picked.append(col)
                if len(picked) >= _MAX_STAT_COLUMNS:
                    return

    _match(_DATE_HINTS)
    _match(_MEASURE_HINTS)
    _match(_KEY_HINTS)
    return picked[:_MAX_STAT_COLUMNS]


def _quote(source: str, ident: str) -> str:
    if source == "postgres":
        return f'"{ident}"'
    return f"[{ident}]"


def _table_sql_ref(source: str, table_ref: str) -> str:
    parts = table_ref.split(".", 1)
    if len(parts) == 2:
        return f"{_quote(source, parts[0])}.{_quote(source, parts[1])}"
    return _quote(source, table_ref)


def _sample_sql(source: str, table_ref: str, columns: list[str]) -> str:
    cols = ", ".join(_quote(source, c) for c in columns)
    ref = _table_sql_ref(source, table_ref)
    if source == "postgres":
        return f"SELECT {cols} FROM {ref} LIMIT {_SAMPLE_ROWS}"
    return f"SELECT TOP {_SAMPLE_ROWS} {cols} FROM {ref}"


def _minmax_sql(source: str, table_ref: str, column: str) -> str:
    col = _quote(source, column)
    ref = _table_sql_ref(source, table_ref)
    return f"SELECT MIN({col}) AS min_value, MAX({col}) AS max_value FROM {ref}"


def _column_stats_from_sample(rows: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    """Null %, distinct count, min/max computed locally from a bounded sample."""
    n = len(rows)
    stats: list[dict[str, Any]] = []
    for col in columns:
        values = [r.get(col) for r in rows]
        non_null = [v for v in values if v is not None and str(v).strip() != ""]
        distinct = {str(v) for v in non_null}
        numeric_values: list[float] = []
        for v in non_null:
            try:
                numeric_values.append(float(v))
            except (TypeError, ValueError):
                numeric_values = []
                break
        entry: dict[str, Any] = {
            "column": col,
            "sample_size": n,
            "null_pct": round(100.0 * (n - len(non_null)) / n, 1) if n else None,
            "distinct_in_sample": len(distinct),
        }
        if numeric_values:
            entry["min"] = min(numeric_values)
            entry["max"] = max(numeric_values)
            entry["is_numeric_content"] = True
        stats.append(entry)
    return stats


def _pick_date_range_column(profile: dict[str, Any]) -> str | None:
    cols = [str(c.get("COLUMN_NAME", "")) for c in profile.get("columns", [])]
    for preferred in ("SourceMonth", "Fiscal_Year", "Posting_Date"):
        if preferred in cols:
            return preferred
    for col in cols:
        if "date" in col.lower():
            return col
    return None


def _verified_metrics_for_theme(theme_name: str) -> list[dict[str, Any]]:
    """Glossary metric.* entries visible to prompts for this theme."""
    path = _path_for("glossary")
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = doc.get("items", [])
    out: list[dict[str, Any]] = []
    for item in items:
        if theme_name and item.get("theme") and item.get("theme") != theme_name:
            continue
        if not _visible_to_prompts(item):
            continue
        key = str(item.get("field_key") or "")
        if key.startswith("metric."):
            out.append(
                {
                    "metric_key": key,
                    "table_name": item.get("table_name", ""),
                    "definition_th": item.get("definition_th", ""),
                    "status": item.get("status", "draft"),
                    "source": item.get("source", ""),
                }
            )
    return out


def _join_candidates(discovery: dict[str, Any], theme_name: str) -> list[dict[str, Any]]:
    """Discovery heuristics + knowledge relationships, flagged for confirmation."""
    joins: list[dict[str, Any]] = []
    for rel in discovery.get("relationships", []) or []:
        joins.append(
            {
                "column": rel.get("column", ""),
                "tables": rel.get("tables", []),
                "confidence": rel.get("confidence", "medium"),
                "evidence": rel.get("note", "shared key column name (heuristic)"),
                "needs_confirmation": True,
            }
        )
    rel_path = _path_for("relationships")
    if rel_path.exists():
        doc = json.loads(rel_path.read_text(encoding="utf-8"))
        for item in doc.get("items", []):
            if theme_name and item.get("theme") and item.get("theme") != theme_name:
                continue
            if not _visible_to_prompts(item):
                continue
            joins.append(
                {
                    "from_table": item.get("from_table", ""),
                    "to_table": item.get("to_table", ""),
                    "join_keys": item.get("join_keys", ""),
                    "confidence": "high" if item.get("status") == "approved" else "medium",
                    "evidence": f"knowledge store ({item.get('source') or 'manual'}, {item.get('status', 'draft')})",
                    "needs_confirmation": item.get("status") != "approved",
                }
            )
    return joins


def _build_dq_issues(
    profiles: list[dict[str, Any]],
    column_stats: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for p in profiles:
        table = p.get("table", "")
        if p.get("row_count") == 0:
            issues.append(
                {"table": table, "issue": "empty_table", "detail_th": "ตารางไม่มีข้อมูล (0 แถว)"}
            )
        varchar_measures = [
            str(c.get("COLUMN_NAME"))
            for c in p.get("columns", [])
            if "varchar" in str(c.get("DATA_TYPE", "")).lower()
            and any(h in str(c.get("COLUMN_NAME", "")).lower() for h in _MEASURE_HINTS)
        ]
        if varchar_measures:
            issues.append(
                {
                    "table": table,
                    "issue": "varchar_measure_columns",
                    "detail_th": (
                        "คอลัมน์ตัวเลขถูกเก็บเป็น varchar — ต้อง CAST ก่อนคำนวณ: "
                        + ", ".join(varchar_measures[:8])
                    ),
                }
            )
    for table, stats in column_stats.items():
        for s in stats:
            if s.get("null_pct") is not None and s["null_pct"] >= 50.0:
                issues.append(
                    {
                        "table": table,
                        "issue": "high_null_column",
                        "detail_th": f"คอลัมน์ {s['column']} มี null/ว่าง {s['null_pct']}% ใน sample",
                    }
                )
    return issues


def _role_homework(
    profiles: list[dict[str, Any]],
    table_roles: dict[str, str],
    metrics: list[dict[str, Any]],
    dq_issues: list[dict[str, Any]],
    date_ranges: dict[str, dict[str, Any]],
    baseline_sql: list[str],
    theme_name: str,
) -> dict[str, Any]:
    """Deterministic per-role homework notes — hypotheses, not findings."""
    facts = [t for t, r in table_roles.items() if r == "fact"]
    dims = [t for t, r in table_roles.items() if r == "dimension"]

    ds_hypotheses = []
    if metrics:
        first_metrics = ", ".join(m["metric_key"] for m in metrics[:4])
        ds_hypotheses.append(
            f"ทดสอบแนวโน้มรายเดือน (MoM trend) ของ metric ที่ owner ยืนยัน: {first_metrics}"
        )
        ds_hypotheses.append(
            "ตรวจ concentration (Pareto 80/20) ของกำไร/รายได้ตาม Profit_Center และ Plant"
        )
        ds_hypotheses.append(
            "ตรวจ outlier รายเดือน (เดือนที่ยอดเบี่ยงจากค่าเฉลี่ยเกิน 2 SD) ก่อนสรุปแนวโน้ม"
        )
    if any(i["issue"] == "empty_table" for i in dq_issues):
        ds_hypotheses.append("ตรวจสอบตารางว่าง — อาจกระทบ join/coverage ของการวิเคราะห์")

    return {
        "data_engineer": {
            "focus_th": "โครงสร้าง + คุณภาพข้อมูล",
            "tables_profiled": len(profiles),
            "fact_tables": facts,
            "dimension_tables": dims,
            "dq_issues_found": len(dq_issues),
            "notes_th": [
                f"จำแนกบทบาทตาราง (fact/dimension) จาก row count + naming แล้ว {len(table_roles)} ตาราง",
                f"พบประเด็นคุณภาพข้อมูล {len(dq_issues)} รายการ (ดู data_quality_issues)",
            ],
        },
        "data_scientist": {
            "focus_th": "สมมติฐาน + การตรวจเชิงสถิติ (ยังไม่ใช่ผลการวิเคราะห์)",
            "hypotheses_th": ds_hypotheses,
            "statistical_checks_th": [
                "null/cardinality ต่อคอลัมน์จาก sample ที่จำกัดขนาด (ดู column_stats)",
                "ช่วงเวลาข้อมูล (min–max) ต่อตาราง fact (ดู date_ranges)",
            ],
            "note_th": (
                "ระบบนี้เป็น LLM orchestration + deterministic profiling — "
                "ยังไม่มีการเทรนโมเดล ML จริง"
            ),
        },
        "data_analyst": {
            "focus_th": "SQL พื้นฐานที่ใช้ profile จริง (read-only, bounded)",
            "baseline_sql": baseline_sql[:6],
            "date_ranges": date_ranges,
        },
        "business_analyst": {
            "focus_th": "นิยามธุรกิจ + คำถามที่ควรถามต่อ",
            "verified_metrics": [m["metric_key"] for m in metrics][:10],
            "questions_th": [
                f"นิยาม metric ของ theme {theme_name or '-'} ตรงกับรายงานทางการหรือไม่?",
                "ช่วงเวลาข้อมูลครอบคลุมรอบบัญชีที่ต้องรายงานหรือไม่?",
                "ตารางว่าง/คอลัมน์ null สูง มีผลต่อ KPI ใดบ้าง?",
            ],
        },
    }


def build_homework(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    """Build + persist the deep-profiling homework artifact for a theme.

    Requires discovery on disk. Live queries are attempted only when a source
    is reachable and stop after a wall-clock budget; every failure degrades
    gracefully and is recorded in the artifact.
    """
    discovery = load_discovery(theme_id)
    if not discovery:
        raise ValueError(f"No discovery for theme {theme_id} — run discovery first")

    started = time.monotonic()
    source = get_active_sql_source()
    evidence_level = EVIDENCE_LEVELS.get(source, "disk_cache")
    profiles = discovery.get("profiles", []) or []

    table_roles = {p.get("table", ""): classify_table_role(p) for p in profiles}
    focus = _pick_focus_tables(profiles)
    live_errors: list[str] = []
    date_ranges: dict[str, dict[str, Any]] = {}
    column_stats: dict[str, list[dict[str, Any]]] = {}
    baseline_sql: list[str] = []

    def _budget_left() -> bool:
        return (time.monotonic() - started) < _LIVE_BUDGET_SECONDS

    if source != "offline":
        for profile in focus:
            table_ref = profile.get("table", "")
            if not table_ref or not _budget_left():
                break
            date_col = _pick_date_range_column(profile)
            if date_col:
                sql = _minmax_sql(source, table_ref, date_col)
                baseline_sql.append(sql)
                try:
                    result = run_sql(sql, mode="deep_profile", max_rows=1, source=source)
                    rows = result.get("rows") or []
                    if rows:
                        date_ranges[table_ref] = {
                            "column": date_col,
                            "min": rows[0].get("min_value"),
                            "max": rows[0].get("max_value"),
                        }
                except Exception as exc:
                    logger.warning("Homework date-range failed %s: %s", table_ref, exc)
                    live_errors.append(f"date_range {table_ref}: {type(exc).__name__}")

            if not _budget_left():
                break
            cols = _interesting_columns(profile)
            if cols:
                sql = _sample_sql(source, table_ref, cols)
                baseline_sql.append(sql)
                try:
                    result = run_sql(
                        sql, mode="deep_profile", max_rows=_SAMPLE_ROWS, source=source
                    )
                    column_stats[table_ref] = _column_stats_from_sample(
                        result.get("rows") or [], cols
                    )
                except Exception as exc:
                    logger.warning("Homework sample stats failed %s: %s", table_ref, exc)
                    live_errors.append(f"column_stats {table_ref}: {type(exc).__name__}")

        if live_errors and not date_ranges and not column_stats:
            evidence_level = "disk_cache"

    metrics = _verified_metrics_for_theme(theme_name)
    dq_issues = _build_dq_issues(profiles, column_stats)
    joins = _join_candidates(discovery, theme_name)

    artifact = {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "generated_at": _utc_now(),
        "source": source,
        "evidence_level": evidence_level,
        "discovery_freshness": discovery.get("discovered_at"),
        "duration_seconds": round(time.monotonic() - started, 1),
        "table_roles": table_roles,
        "row_counts": {p.get("table", ""): p.get("row_count") for p in profiles},
        "date_ranges": date_ranges,
        "column_stats": column_stats,
        "verified_metrics": metrics,
        "join_candidates": joins,
        "data_quality_issues": dq_issues,
        "live_errors": live_errors,
        "role_homework": _role_homework(
            profiles, table_roles, metrics, dq_issues, date_ranges, baseline_sql, theme_name
        ),
        "method_note_th": (
            "หลักฐานนี้มาจาก deterministic profiling (query จริงแบบจำกัดขอบเขต + metadata) "
            "ไม่ใช่ผลจากโมเดล machine learning"
        ),
    }
    _save_homework(theme_id, artifact)
    logger.info(
        "Homework built theme=%s evidence=%s tables=%s live_errors=%s in %ss",
        theme_id,
        evidence_level,
        len(profiles),
        len(live_errors),
        artifact["duration_seconds"],
    )
    return artifact


def format_homework_context(theme_id: str, max_chars: int = 2500) -> str:
    """Compact evidence summary for agent prompts. Empty string when absent."""
    data = load_homework(theme_id)
    if not data:
        return ""
    lines: list[str] = [
        "## Data Homework Evidence (deterministic profiling — verified numbers)",
        f"Source: {data.get('source')} · evidence: {data.get('evidence_level')} · at {str(data.get('generated_at'))[:19]}",
    ]
    roles = data.get("table_roles") or {}
    counts = data.get("row_counts") or {}
    for table, role in list(roles.items())[:10]:
        rc = counts.get(table)
        rc_txt = f"{rc:,}" if isinstance(rc, int) else "?"
        extra = ""
        rng = (data.get("date_ranges") or {}).get(table)
        if rng:
            extra = f" · {rng.get('column')}: {rng.get('min')}→{rng.get('max')}"
        lines.append(f"- {table}: {role}, rows={rc_txt}{extra}")
    dq = data.get("data_quality_issues") or []
    if dq:
        lines.append("Data-quality flags:")
        for issue in dq[:6]:
            lines.append(f"- [{issue.get('table')}] {issue.get('detail_th')}")
    metrics = data.get("verified_metrics") or []
    if metrics:
        lines.append(f"Verified metrics available: {', '.join(m['metric_key'] for m in metrics[:8])}")
    text = "\n".join(lines)
    return text[:max_chars]
