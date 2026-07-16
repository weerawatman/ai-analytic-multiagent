"""Seed sales theme glossary and targets with correct UTF-8."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.services.local_paths import ensure_local_structure, get_local_dir

THEME = "ยอดขายและลูกค้า"

GLOSSARY = [
    {
        "field_key": "VBRK_All_Cleaned.Billing_Date",
        "table_name": "SAPHANADB.VBRK_All_Cleaned",
        "definition_th": "วันที่ออกใบแจ้งหนี้ (SAP FKDAT) — ใช้กรองยอดขายรายเดือน",
        "theme": THEME,
        "status": "approved",
    },
    {
        "field_key": "VBRK_All_Cleaned.Net_Value_In_Document_Currency",
        "table_name": "SAPHANADB.VBRK_All_Cleaned",
        "definition_th": "ยอดขายสุทธิใน document currency (SAP NETWR)",
        "theme": THEME,
        "status": "approved",
    },
    {
        "field_key": "VBRK_All_Cleaned.Fiscal_Year",
        "table_name": "SAPHANADB.VBRK_All_Cleaned",
        "definition_th": "ปีบัญชี",
        "theme": THEME,
        "status": "approved",
    },
    {
        "field_key": "VBRK_All_Cleaned.SourceMonth",
        "table_name": "SAPHANADB.VBRK_All_Cleaned",
        "definition_th": "เดือนที่ load ข้อมูล (YYYYMM)",
        "theme": THEME,
        "status": "draft",
    },
    {
        "field_key": "VBRK_All_Cleaned.Sold_To_Party",
        "table_name": "SAPHANADB.VBRK_All_Cleaned",
        "definition_th": "ลูกค้าที่ซื้อ — join Dim_KNA1_Cleaned",
        "theme": THEME,
        "status": "draft",
    },
    {
        "field_key": "metric.sales_monthly",
        "definition_th": "ยอดขาย = SUM(Net_Value_In_Document_Currency) GROUP BY เดือนจาก Billing_Date",
        "theme": THEME,
        "status": "approved",
    },
]

TARGETS = [
    {
        "name_th": "ยอดขาย 2026 รายเดือน",
        "description_th": "วิเคราะห์ยอดขายสุทธิรายเดือนในปี 2026 grain=month",
        "theme": THEME,
        "status": "approved",
    },
]


def _stamp(items: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for item in items:
        out.append(
            {
                "id": str(uuid4()),
                "created_at": now,
                "updated_at": now,
                **item,
            }
        )
    return out


def main() -> None:
    ensure_local_structure()
    knowledge_dir = get_local_dir() / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    glossary_path = knowledge_dir / "glossary.json"
    targets_path = knowledge_dir / "targets.json"

    glossary_path.write_text(
        json.dumps({"version": "1.0", "items": _stamp(GLOSSARY)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    targets_path.write_text(
        json.dumps({"version": "1.0", "items": _stamp(TARGETS)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"glossary": len(GLOSSARY), "targets": len(TARGETS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
