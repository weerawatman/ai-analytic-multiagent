"""Proactive Insight Starter Pack — deterministic, evidence-labeled.

After onboarding (or on demand) the team persists 3–5 concrete candidate
insights for the theme's main fact table, each built from owner-verified
metric definitions in the knowledge store:

- hypothesis (Thai) — clearly a hypothesis, never presented as a finding
- SQL + fields needed (cross-dialect: no TOP/LIMIT tricks in aggregates)
- expected business decision the answer supports
- evidence_status: ``not_run`` | ``validated`` | ``failed``
- confidence

At most ONE baseline trend query is executed live (read-only, single-digit
result rows, bounded by the existing SQL guard/timeouts); its aggregate rows
are stored — never row-level data. Everything else stays ``not_run`` until a
human/agent runs it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger
from backend.app.services.deep_profile_service import classify_table_role
from backend.app.services.discovery_service import load_discovery
from backend.app.services.fabric_sql import get_active_sql_source, run_sql
from backend.app.services.knowledge_store import _path_for, _visible_to_prompts
from backend.app.services.local_paths import get_local_dir

# Identifier-expression prefix inside a "Fabric cleaned:" definition segment,
# e.g. "(Inter_Company + Revenue + Return_Revenue) - COGS_Actual".
_EXPR_RE = re.compile(r"^[A-Za-z0-9_+\-() ]+")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _starter_path(theme_id: str) -> Path:
    path = get_local_dir() / "knowledge" / "themes" / theme_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "insight_starter.json"


def load_starter_pack(theme_id: str) -> dict[str, Any] | None:
    path = _starter_path(theme_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save(theme_id: str, data: dict[str, Any]) -> dict[str, Any]:
    path = _starter_path(theme_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)
    return data


def parse_cleaned_expression(definition_th: str, valid_columns: set[str]) -> str | None:
    """Extract the Fabric-cleaned column expression from an owner definition.

    Returns the expression only when every identifier is a real column of the
    target table — a guess must never silently become SQL.
    """
    marker = "Fabric cleaned:"
    idx = definition_th.find(marker)
    if idx == -1:
        return None
    tail = definition_th[idx + len(marker):].split("|")[0].strip()
    match = _EXPR_RE.match(tail)
    if not match:
        return None
    expr = match.group(0).strip().rstrip("+-( ").strip()
    idents = _IDENT_RE.findall(expr)
    if not idents:
        return None
    if any(ident not in valid_columns for ident in idents):
        return None
    return expr


def _metric_items(theme_name: str) -> list[dict[str, Any]]:
    path = _path_for("glossary")
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for item in doc.get("items", []):
        if theme_name and item.get("theme") and item.get("theme") != theme_name:
            continue
        if not _visible_to_prompts(item):
            continue
        if str(item.get("field_key", "")).startswith("metric."):
            out.append(item)
    return out


def _registry_expressions(theme_name: str, valid_columns: set[str]) -> dict[str, str]:
    """Prefer Phase G2 Metric Registry (approved, non-derived) over glossary."""
    from backend.app.services.metric_registry import load_registry_sync

    out: dict[str, str] = {}
    doc = load_registry_sync()
    for m in doc.get("metrics") or []:
        if m.get("status") != "approved":
            continue
        if m.get("derived") or not m.get("expression"):
            continue
        m_theme = m.get("theme")
        if theme_name and m_theme and m_theme not in (theme_name, "Saphanadb"):
            continue
        expr = str(m["expression"])
        idents = _IDENT_RE.findall(expr)
        if idents and any(i not in valid_columns for i in idents):
            continue
        out[str(m["metric_key"])] = expr
    return out


def _main_fact_profile(discovery: dict[str, Any]) -> dict[str, Any] | None:
    facts = [p for p in discovery.get("profiles", []) if classify_table_role(p) == "fact"]
    if not facts:
        return None
    facts.sort(key=lambda p: p.get("row_count") or 0, reverse=True)
    # Prefer CE1SATG-style CO-PA fact tables when present.
    for p in facts:
        if "ce1satg" in str(p.get("table", "")).lower():
            return p
    return facts[0]


def _month_column(profile: dict[str, Any]) -> str | None:
    cols = {str(c.get("COLUMN_NAME", "")) for c in profile.get("columns", [])}
    for preferred in ("SourceMonth", "Period_Year"):
        if preferred in cols:
            return preferred
    return None


def _quote_table(source: str, table_ref: str) -> str:
    q = ('"', '"') if source == "postgres" else ("[", "]")
    parts = table_ref.split(".", 1)
    return ".".join(f"{q[0]}{p}{q[1]}" for p in parts)


def build_starter_pack(
    theme_id: str,
    theme_name: str = "",
    *,
    execute_baseline: bool = True,
) -> dict[str, Any]:
    """Build + persist the starter pack; optionally run ONE baseline query."""
    discovery = load_discovery(theme_id)
    if not discovery:
        raise ValueError(f"No discovery for theme {theme_id} — run discovery first")

    fact = _main_fact_profile(discovery)
    source = get_active_sql_source()
    items: list[dict[str, Any]] = []
    note_th = ""

    if fact is None:
        note_th = "ยังไม่พบตาราง fact ใน discovery — สร้าง starter pack ไม่ได้"
    else:
        table_ref = str(fact.get("table"))
        columns = {str(c.get("COLUMN_NAME", "")) for c in fact.get("columns", [])}
        month_col = _month_column(fact)
        expressions: dict[str, str] = _registry_expressions(theme_name, columns)
        # Glossary Fabric-cleaned formulas remain as fallback for keys not in registry
        for m in _metric_items(theme_name):
            key = str(m["field_key"])
            if key in expressions:
                continue
            expr = parse_cleaned_expression(str(m.get("definition_th", "")), columns)
            if expr:
                expressions[key] = expr

        items = _build_items(table_ref, month_col, expressions, source)
        if not items:
            note_th = (
                "ไม่มี metric ที่ยืนยันสูตร (registry / Fabric cleaned) ที่ตรงกับคอลัมน์จริง — "
                "seed Metric Registry หรือเพิ่ม glossary metric ก่อน"
            )

    executed = None
    if items and execute_baseline and source != "offline":
        executed = _execute_baseline(items[0], source)

    pack = {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "generated_at": _utc_now(),
        "source": source,
        "note_th": note_th,
        "items": items,
        "method_note_th": (
            "สร้างจาก Metric Registry (approved) + glossary fallback (deterministic) — "
            "รายการที่ evidence_status=not_run เป็นเพียงสมมติฐาน ยังไม่ใช่ข้อค้นพบ"
        ),
    }
    _save(theme_id, pack)
    logger.info(
        "Starter pack built theme=%s items=%s baseline=%s source=%s",
        theme_id,
        len(items),
        (executed or {}).get("evidence_status") if executed else "skipped",
        source,
    )
    return pack


def _build_items(
    table_ref: str,
    month_col: str | None,
    expressions: dict[str, str],
    source: str,
) -> list[dict[str, Any]]:
    if not month_col or not expressions:
        return []
    table_sql = _quote_table(source, table_ref)
    rev = expressions.get("metric.revenue_plus_inter")
    gp = expressions.get("metric.gross_profit")
    cm = expressions.get("metric.contribution_margin")

    items: list[dict[str, Any]] = []

    if rev and gp:
        items.append(
            {
                "id": "baseline_trend_6m",
                "title_th": "แนวโน้ม Revenue +Inter และ Gross Profit รายเดือน (6 เดือนล่าสุด)",
                "hypothesis_th": (
                    "Gross Profit รายเดือนมีแนวโน้มคงที่หรือดีขึ้นใน 6 เดือนล่าสุด — "
                    "ถ้าเดือนใดตกแรง ควรเจาะ Profit_Center/Plant ต่อ"
                ),
                "sql": (
                    f"SELECT {month_col},\n"
                    f"  SUM({rev}) AS revenue_plus_inter,\n"
                    f"  SUM(COGS_Actual) AS cogs_actual,\n"
                    f"  SUM({gp}) AS gross_profit\n"
                    f"FROM {table_sql}\n"
                    f"WHERE {month_col} >= '{{cutoff}}'\n"
                    f"GROUP BY {month_col}\n"
                    f"ORDER BY {month_col}"
                ),
                "fields_needed": sorted(set(_IDENT_RE.findall(f"{rev} {gp}")) | {month_col}),
                "expected_decision_th": "ตัดสินใจว่าจะเจาะเดือน/หน่วยงานไหนต่อ และตั้งเป้า GP รายเดือน",
                "evidence_status": "not_run",
                "confidence": "high",
                "metric_keys": ["metric.revenue_plus_inter", "metric.gross_profit"],
            }
        )
    if cm:
        items.append(
            {
                "id": "contribution_margin_trend",
                "title_th": "Contribution Margin รายเดือน (สูตร owner: KFG0002 - KFG0006)",
                "hypothesis_th": "Con.Margin ต่อเดือนสะท้อนต้นทุนผันแปร — เดือนที่ margin บีบตัวควรตรวจ COGS Vc รายก้อน",
                "sql": (
                    f"SELECT {month_col}, SUM({cm}) AS contribution_margin\n"
                    f"FROM {table_sql}\n"
                    f"WHERE {month_col} >= '{{cutoff}}'\n"
                    f"GROUP BY {month_col}\nORDER BY {month_col}"
                ),
                "fields_needed": sorted(set(_IDENT_RE.findall(cm)) | {month_col}),
                "expected_decision_th": "ชี้เป้าการควบคุมต้นทุนผันแปร (วัตถุดิบ/แรงงาน/พลังงาน)",
                "evidence_status": "not_run",
                "confidence": "high",
                "metric_keys": ["metric.contribution_margin"],
            }
        )
    if rev:
        items.append(
            {
                "id": "profit_center_pareto",
                "title_th": "Pareto รายได้ตาม Profit Center (เดือนล่าสุด)",
                "hypothesis_th": "รายได้กระจุกตัวใน Profit Center ส่วนน้อย (80/20) — โฟกัสหน่วยที่ขับเคลื่อนกำไรจริง",
                "sql": (
                    f"SELECT Profit_Center, SUM({rev}) AS revenue_plus_inter\n"
                    f"FROM {table_sql}\n"
                    f"WHERE {month_col} = '{{latest_month}}'\n"
                    f"GROUP BY Profit_Center\nORDER BY revenue_plus_inter DESC"
                ),
                "fields_needed": sorted(set(_IDENT_RE.findall(rev)) | {month_col, "Profit_Center"}),
                "expected_decision_th": "จัดลำดับความสำคัญของหน่วยธุรกิจในการรีวิวผลประกอบการ",
                "evidence_status": "not_run",
                "confidence": "medium",
                "metric_keys": ["metric.revenue_plus_inter"],
            }
        )
    if gp:
        items.append(
            {
                "id": "negative_gp_months",
                "title_th": "เดือนที่ Gross Profit ติดลบ (data-quality / ธุรกิจ)",
                "hypothesis_th": "ถ้ามีเดือนที่ GP ติดลบ อาจเป็น one-off cost หรือปัญหาคุณภาพข้อมูล — ต้อง validate กับ BA",
                "sql": (
                    f"SELECT {month_col}, SUM({gp}) AS gross_profit\n"
                    f"FROM {table_sql}\n"
                    f"GROUP BY {month_col}\n"
                    f"HAVING SUM({gp}) < 0\nORDER BY {month_col}"
                ),
                "fields_needed": sorted(set(_IDENT_RE.findall(gp)) | {month_col}),
                "expected_decision_th": "แยกปัญหาข้อมูลออกจากปัญหาธุรกิจก่อนรายงานผู้บริหาร",
                "evidence_status": "not_run",
                "confidence": "medium",
                "metric_keys": ["metric.gross_profit"],
            }
        )
    return items


def _resolve_cutoff(item: dict[str, Any], source: str, table_sql_month: tuple[str, str]) -> str | None:
    """MAX(month) - 5 months, derived live so the window follows the data."""
    table_sql, month_col = table_sql_month
    try:
        result = run_sql(
            f"SELECT MAX({month_col}) AS max_month FROM {table_sql}",
            mode="starter_pack",
            max_rows=1,
            source=source,
        )
        rows = result.get("rows") or []
        max_month = str(rows[0].get("max_month") or "") if rows else ""
        if len(max_month) == 6 and max_month.isdigit():
            year, month = int(max_month[:4]), int(max_month[4:])
            month -= 5
            while month <= 0:
                month += 12
                year -= 1
            return f"{year:04d}{month:02d}"
    except Exception as exc:
        logger.warning("Starter pack cutoff resolution failed: %s", exc)
    return None


def _execute_baseline(item: dict[str, Any], source: str) -> dict[str, Any]:
    """Run the single baseline trend query read-only; store aggregates only."""
    sql_template = item.get("sql", "")
    match = re.search(r"FROM\s+(\S+)", sql_template)
    month_match = re.search(r"GROUP BY\s+(\w+)", sql_template)
    if not match or not month_match:
        return item
    cutoff = _resolve_cutoff(item, source, (match.group(1), month_match.group(1)))
    if not cutoff:
        item["evidence_status"] = "failed"
        item["evidence_note_th"] = "หา cutoff เดือนล่าสุดไม่สำเร็จ — ยังไม่รัน baseline"
        return item
    sql = sql_template.replace("{cutoff}", cutoff)
    try:
        result = run_sql(sql, mode="starter_pack", max_rows=12, source=source)
        rows = result.get("rows") or []
        item["evidence_status"] = "validated"
        item["executed_at"] = _utc_now()
        item["executed_source"] = result.get("source", source)
        item["executed_sql"] = sql
        item["result_rows"] = rows[:12]
        item["evidence_note_th"] = f"รันจริงแล้ว {len(rows)} เดือน (aggregate เท่านั้น)"
    except Exception as exc:
        logger.warning("Starter pack baseline failed: %s", exc)
        item["evidence_status"] = "failed"
        item["evidence_note_th"] = f"รัน baseline ไม่สำเร็จ ({type(exc).__name__})"
    return item
