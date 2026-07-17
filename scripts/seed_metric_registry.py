"""Seed ~15 CE1SATG metrics into the Metric Registry (Phase G2).

Owner decisions 2026-07-18:
- O-1 Net Profit: BA has not given a formula yet — `metric.net_profit` stays draft.
- O-2 Discount rate: provisional approved — Price_Adjustment / Revenue (pending BA).
- O-3 Time base: SourceMonth (YYYYMM) verified equivalent to Fiscal_Year+Period
  (Period_Year = GJAHR||PERDE composite) — QoQ/YoY approved on SourceMonth.
Known formulas from the glossary "Fabric cleaned:" definitions are seeded as approved.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.app.services.local_paths import ensure_local_structure, get_local_dir, get_templates_dir
from backend.app.services import metric_registry

THEME = "Saphanadb"
TABLE = "SAPHANADB.CE1SATG_All_Cleaned"
DIMS = [
    "Customer",
    "Product_Number",
    "Profit_Center",
    "Sales_Organization",
    "Material_Group_MATKL",
]

REV_PLUS = (
    "(CAST(Inter_Company AS DECIMAL(18,2)) + CAST(Revenue AS DECIMAL(18,2)) "
    "+ CAST(Return_Revenue AS DECIMAL(18,2)))"
)
# Seed expressions use uncast column names — render_metric_sql applies CAST.
REV_PLUS_RAW = "(Inter_Company + Revenue + Return_Revenue)"
GP_RAW = f"({REV_PLUS_RAW}) - COGS_Actual"

# O-3 (2026-07-18): เทียบจาก usp_Load_CE1SATG_Month — Period_Year=PERIO,
# Fiscal_Year=GJAHR, Period=PERDE; ตัวอย่างจริงจาก discovery profile:
# Period_Year='2025005' = Fiscal_Year '2025' + Period '005' และ SourceMonth='202505'
_O3_TIME_BASE_NOTE = (
    "O-3 RESOLVED (2026-07-18): owner เลือกฐานเวลา fiscal. ตรวจแล้ว Period_Year (PERIO) "
    "คือ Fiscal_Year (GJAHR) + Period (PERDE) ต่อกัน เช่น '2025005' = '2025'+'005' "
    "และตรงกับ SourceMonth '202505' — จึงใช้ SourceMonth (YYYYMM) เป็น time_column ได้ "
    "เพราะเทียบเท่า Fiscal_Year+Period ที่ granularity เดือน"
)


def _base(
    key: str,
    name_th: str,
    name_en: str,
    *,
    expression: str | None,
    status: str,
    tags: list[str],
    derived: dict | None = None,
    unit: str = "THB",
    aggregation: str = "SUM",
    owner_confirmed: bool = False,
    notes: str | None = None,
    change_reason: str | None = None,
) -> dict:
    entry = {
        "metric_key": key,
        "name_th": name_th,
        "name_en": name_en,
        "version": 1,
        "status": status,
        "theme": THEME,
        "table": TABLE,
        "time_column": "SourceMonth",
        "time_format": "YYYYMM",
        "expression": expression,
        "aggregation": aggregation,
        "dimensions": list(DIMS),
        "unit": unit,
        "derived": derived,
        "baseline_question_tags": tags,
        "source": "owner_seed",
        "owner_confirmed": owner_confirmed,
    }
    if notes is not None:
        entry["notes"] = notes
    if change_reason is not None:
        entry["change_reason"] = change_reason
    return entry


SEED_METRICS: list[dict] = [
    _base(
        "metric.revenue",
        "รายได้",
        "Revenue",
        expression="Revenue",
        status="approved",
        tags=["revenue"],
        owner_confirmed=True,
    ),
    _base(
        "metric.revenue_plus_inter",
        "รายได้รวม Inter Company",
        "Revenue + Inter-Company",
        expression=REV_PLUS_RAW,
        status="approved",
        tags=["revenue", "revenue_plus_inter"],
        owner_confirmed=True,
    ),
    _base(
        "metric.gross_profit",
        "กำไรขั้นต้น",
        "Gross Profit",
        expression=GP_RAW,
        status="approved",
        tags=["gross_profit", "qoq", "yoy"],
        owner_confirmed=True,
    ),
    _base(
        "metric.gp_pct",
        "อัตรากำไรขั้นต้น",
        "Gross Profit %",
        expression=None,
        status="approved",
        tags=["gross_profit", "gp_pct"],
        derived={"kind": "ratio", "of": "metric.gross_profit", "over": "metric.revenue_plus_inter"},
        unit="pct",
        owner_confirmed=True,
    ),
    _base(
        "metric.net_profit",
        "กำไรสุทธิ",
        "Net Profit",
        expression=None,  # O-1 — BA has not provided the formula yet (2026-07-18)
        status="draft",
        tags=["net_profit"],
        owner_confirmed=False,
        notes=(
            "O-1 ยังเปิดอยู่ (2026-07-18): BA ยังไม่ให้สูตร Net Profit — ห้ามเดาสูตรเอง. "
            "สูตรธุรกิจที่ owner ยืนยันแล้ว (source of truth ใน glossary): "
            "COGS-Act Vc=KFG0006=VVA02+VVA03+VVA04+VVA08+VVA05+VVA06+VVA10+VVA12+VVA11+VVA07+VVA09; "
            "COGS-Act Fc=VVA13+VVA14+VVA16+VVA15+VVA17+VVA19+VVA20+VVA21+VVA22 (ไม่รวม VVA18); "
            "COGS-Actual (business)=Vc+Fc (คนละตัวกับคอลัมน์ COGS_Actual=VVA01); "
            "Con. Margin=KFG0002-KFG0006; Gross Profit=KFG0002-VVA01; "
            "GP Inc. Defect=KFG0002-VVA01-VVC01; Revenue +Inter=KFG0002=VVR06+ERLOS+VVR01"
        ),
    ),
    _base(
        "metric.sales_quantity",
        "ปริมาณขาย",
        "Sales Quantity",
        expression="Sales_Quantity",
        status="approved",
        tags=["sales_quantity"],
        unit="qty",
        owner_confirmed=True,
    ),
    _base(
        "metric.sales_per_customer",
        "ยอดขายต่อลูกค้า",
        "Sales per Customer",
        expression=None,
        status="approved",
        tags=["sales_per_customer"],
        derived={
            "kind": "ratio",
            "of": "metric.revenue_plus_inter",
            "over": "metric.customer_count",
        },
        owner_confirmed=True,
    ),
    _base(
        "metric.customer_count",
        "จำนวนลูกค้า",
        "Customer Count",
        expression="Customer",
        status="approved",
        tags=["customer"],
        aggregation="COUNT",
        unit="count",
        owner_confirmed=True,
    ),
    _base(
        "metric.product_champion",
        "สินค้าแชมป์ (รายได้สูงสุด)",
        "Product Champion",
        expression=REV_PLUS_RAW,
        status="approved",
        tags=["product_champion"],
        owner_confirmed=True,
    ),
    _base(
        "metric.price_adjustment",
        "มูลค่าปรับราคา/ส่วนลด",
        "Price Adjustment",
        expression="Price_Adjustment",
        status="approved",
        tags=["discount_rate"],
        owner_confirmed=True,
        notes=(
            "O-2 (2026-07-18): คอลัมน์ Price_Adjustment มีจริงใน CE1SATG_All_Cleaned "
            "(= VVR02 ตามลำดับ CAST ใน usp_Load_CE1SATG_Month; VVR01=Return_Revenue, "
            "VVR04=Price_Adjustment_RM ก็มีแต่ไม่ใช้). ตัวตั้งของ discount rate ชั่วคราว "
            "จนกว่า BA จะยืนยันนิยาม"
        ),
        change_reason="O-2 owner decision 2026-07-18",
    ),
    _base(
        "metric.discount_rate",
        "อัตราส่วนลด",
        "Discount Rate",
        expression=None,
        status="approved",  # O-2 — provisional per owner 2026-07-18
        tags=["discount_rate"],
        derived={"kind": "ratio", "of": "metric.price_adjustment", "over": "metric.revenue"},
        unit="pct",
        owner_confirmed=True,
        notes=(
            "O-2 PROVISIONAL (2026-07-18): owner สั่งใช้ชั่วคราว = Price_Adjustment / Revenue "
            "จนกว่า BA จะยืนยันนิยาม discount rate อย่างเป็นทางการ — ถ้า BA ให้สูตรใหม่ต้อง update "
            "และ bump version. คอลัมน์ Price_Adjustment (VVR02) ยืนยันแล้วว่ามีใน CE1SATG_All_Cleaned"
        ),
        change_reason="O-2 provisional approve (Price_Adjustment / Revenue) per owner 2026-07-18",
    ),
    _base(
        "metric.qoq_revenue",
        "รายได้ QoQ",
        "QoQ Revenue Change",
        expression=None,
        status="approved",  # O-3 resolved 2026-07-18
        tags=["qoq", "revenue"],
        derived={
            "kind": "period_delta",
            "of": "metric.revenue_plus_inter",
            "lag_months": 3,
        },
        unit="pct",
        owner_confirmed=True,
        notes=_O3_TIME_BASE_NOTE,
        change_reason="O-3 fiscal time base verified per owner 2026-07-18",
    ),
    _base(
        "metric.yoy_revenue",
        "รายได้ YoY",
        "YoY Revenue Change",
        expression=None,
        status="approved",  # O-3 resolved 2026-07-18
        tags=["yoy", "revenue"],
        derived={
            "kind": "period_delta",
            "of": "metric.revenue_plus_inter",
            "lag_months": 12,
        },
        unit="pct",
        owner_confirmed=True,
        notes=_O3_TIME_BASE_NOTE,
        change_reason="O-3 fiscal time base verified per owner 2026-07-18",
    ),
    _base(
        "metric.customer_new",
        "ลูกค้าใหม่",
        "New Customers",
        expression="Customer",
        status="approved",
        tags=["customer_new"],
        aggregation="COUNT",
        unit="count",
        owner_confirmed=True,
    ),
    _base(
        "metric.customer_churn",
        "ลูกค้าหาย",
        "Churned Customers",
        expression="Customer",
        status="approved",
        tags=["customer_churn"],
        aggregation="COUNT",
        unit="count",
        owner_confirmed=True,
    ),
]


async def seed(*, force: bool = False) -> dict:
    ensure_local_structure()
    # Also write template copy under data/templates for fresh installs.
    tpl_dir = get_templates_dir() / "knowledge"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = tpl_dir / "metric_registry.template.json"

    created = 0
    updated = 0
    for raw in SEED_METRICS:
        existing = await metric_registry.get_metric(raw["metric_key"])
        if existing and not force:
            continue
        result = await metric_registry.upsert_metric(raw)
        if existing:
            updated += 1
        else:
            created += 1
        _ = result

    doc = metric_registry.load_registry_sync()
    tpl_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    approved = sum(1 for m in doc.get("metrics") or [] if m.get("status") == "approved")
    return {
        "path": str(get_local_dir() / "knowledge" / "metric_registry.json"),
        "created": created,
        "updated": updated,
        "total": len(doc.get("metrics") or []),
        "approved": approved,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed Metric Registry")
    parser.add_argument("--force", action="store_true", help="Overwrite existing entries")
    args = parser.parse_args()
    result = asyncio.run(seed(force=args.force))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
