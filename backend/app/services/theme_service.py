"""Schema scan and theme proposal for Fabric DW exploration."""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services.fabric_connector import FabricConnectionError, get_fabric_connector
from backend.app.services.fabric_sql import (
    fabric_can_query,
    mark_fabric_unreachable,
    mark_pg_unreachable,
    pg_can_query,
)
from backend.app.services.local_paths import get_local_dir
from backend.app.services.postgres_replica import get_postgres_connector

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "sales": [
        "sales", "order", "customer", "invoice", "billing", "revenue",
        "vkorg", "vbap", "vbrk", "kna1", "sold", "delivery",
    ],
    "inventory": [
        "stock", "inventory", "material", "warehouse", "mard", "marc",
        "likp", "goods", "movement", "lips",
    ],
    "finance": [
        "finance", "gl", "account", "cost", "bkpf", "bseg", "fi_",
        "ledger", "payment", "budget",
    ],
    "procurement": [
        "purchase", "vendor", "po", "ekko", "ekpo", "lfb1", "supplier",
    ],
    "production": [
        "production", "plant", "work", "routing", "afko", "aufk", "manufact",
    ],
}

DOMAIN_LABELS_TH: dict[str, dict[str, Any]] = {
    "sales": {
        "name_th": "ยอดขายและลูกค้า",
        "rationale_th": "ตารางที่เกี่ยวกับคำสั่งขาย ลูกค้า และรายได้",
        "starter_questions_th": [
            "ยอดขายรายเดือนมีแนวโน้มอย่างไร?",
            "ลูกค้ากลุ่มไหนซื้อบ่อยที่สุด?",
            "สินค้า top 10 ตามรายได้คืออะไร?",
        ],
    },
    "inventory": {
        "name_th": "สต็อกและวัสดุ",
        "rationale_th": "ตารางที่เกี่ยวกับสต็อก การเคลื่อนไหวสินค้า และคลัง",
        "starter_questions_th": [
            "สินค้าใดมีสต็อกค้างสูง?",
            "อัตราการหมุนเวียนสต็อกเป็นอย่างไร?",
            "มี shortage ที่ plant ไหนบ้าง?",
        ],
    },
    "finance": {
        "name_th": "การเงินและต้นทุน",
        "rationale_th": "ตารางด้านบัญชี ต้นทุน และการเงิน",
        "starter_questions_th": [
            "ต้นทุนหลักมาจากหมวดใด?",
            "รายได้เทียบต้นทุนต่อไตรมาสเป็นอย่างไร?",
            "มีรายการผิดปกติใน GL หรือไม่?",
        ],
    },
    "procurement": {
        "name_th": "จัดซื้อและ Supplier",
        "rationale_th": "ตารางด้านการสั่งซื้อและ vendor",
        "starter_questions_th": [
            "Supplier ใดมีมูลค่าสั่งซื้อสูงสุด?",
            " lead time การจัดซื้อเฉลี่ยเท่าไร?",
            "มี PO ค้างรับที่สำคัญหรือไม่?",
        ],
    },
    "production": {
        "name_th": "การผลิตและ Operations",
        "rationale_th": "ตารางด้านการผลิต plant และ order ผลิต",
        "starter_questions_th": [
            "plant ไหนมี utilization สูงสุด?",
            "order ผลิตล่าช้าเท่าไร?",
            "ของเสีย (scrap) อยู่ที่ระดับไหน?",
        ],
    },
}


def _themes_cache_path() -> Path:
    path = get_local_dir() / "themes"
    path.mkdir(parents=True, exist_ok=True)
    return path / "cached_themes.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _table_key(row: dict[str, Any]) -> str:
    return f"{row.get('table_schema', '')}.{row.get('table_name', '')}"


def cluster_schema_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group tables into domain clusters using keyword heuristics."""
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    other_key = "general"

    for row in rows:
        text = _table_key(row).lower()
        matched = False
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                clusters[domain].append(row)
                matched = True
                break
        if not matched:
            schema = str(row.get("table_schema", "dbo")).lower()
            clusters[schema if schema != "dbo" else other_key].append(row)

    return dict(clusters)


def _heuristic_themes(clusters: dict[str, list[dict[str, Any]]], limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
    themes: list[dict[str, Any]] = []

    for domain, tables in ranked[:limit]:
        meta = DOMAIN_LABELS_TH.get(domain, {})
        name = meta.get("name_th") or domain.replace("_", " ").title()
        sample = [_table_key(t) for t in tables[:8]]
        themes.append(
            {
                "id": domain if domain in DOMAIN_LABELS_TH else str(uuid4())[:8],
                "name_th": name,
                "rationale_th": meta.get(
                    "rationale_th",
                    f"พบตาราง/วิว {len(tables)} รายการในหัวข้อ {domain}",
                ),
                "table_count": len(tables),
                "sample_tables": sample,
                "starter_questions_th": meta.get(
                    "starter_questions_th",
                    [
                        f"ข้อมูลใน {name} มี pattern อะไรน่าสนใจ?",
                        f"metric สำคัญใน {name} ควรเป็นอะไร?",
                        f"ควร validate นิยามใดกับ BA/DA ใน {name}?",
                    ],
                ),
            }
        )

    while len(themes) < limit and ranked:
        # Pad if fewer than 3 clusters
        themes.append(
            {
                "id": f"theme_{len(themes)+1}",
                "name_th": f"หัวข้อสำรวจ {len(themes)+1}",
                "rationale_th": "กลุ่มตารางทั่วไปจาก schema scan",
                "table_count": 0,
                "sample_tables": [],
                "starter_questions_th": ["มีข้อมูลอะไรใน warehouse ที่ควร explore?"],
            }
        )

    return themes[:limit]


async def _enrich_themes_with_llm(
    themes: list[dict[str, Any]],
    schema_sample: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Optional LLM pass to refine Thai labels and questions."""
    llm = make_chat_ollama(temperature=0.2)

    compact_schema = [
        {"schema": r.get("table_schema"), "table": r.get("table_name"), "type": r.get("table_type")}
        for r in schema_sample[:80]
    ]
    prompt = f"""คุณเป็นที่ปรึกษาข้อมูล SAP/Fabric DW
จาก schema sample และ theme candidates ด้านล่าง ปรับปรุง 3 themes ให้เป็นภาษาไทย
คืนค่าเป็น JSON array เท่านั้น (ไม่มี markdown) โดยแต่ละ item มี:
id, name_th, rationale_th, table_count, sample_tables (array), starter_questions_th (array 2-3 ข้อ)

Schema sample:
{json.dumps(compact_schema, ensure_ascii=False)}

Theme candidates:
{json.dumps(themes, ensure_ascii=False)}
"""
    try:
        response = await llm.ainvoke(prompt)
        content = str(response.content).strip()
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            refined: list[dict[str, Any]] = json.loads(match.group())
            if len(refined) >= 1:
                return refined[:3]
    except Exception as exc:
        logger.warning("LLM theme enrichment failed, using heuristic: %s", exc)

    return themes


def load_cached_themes() -> dict[str, Any] | None:
    path = _themes_cache_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_cached_themes(payload: dict[str, Any]) -> dict[str, Any]:
    path = _themes_cache_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return payload


def _fetch_scan_rows() -> tuple[list[dict[str, Any]], str, str]:
    """Fetch schema rows from the first available source.

    Returns (rows, source, database). Fabric is preferred; the Postgres
    WH_Silver mirror is the auto-fallback when Fabric is paused/unreachable
    (Phase F). Raises FabricConnectionError only when no live source worked.
    """
    fabric_connector = get_fabric_connector()
    pg_connector = get_postgres_connector()

    if not fabric_connector.is_configured() and not pg_connector.is_configured():
        raise FabricConnectionError(
            "Fabric not configured",
            "ยังไม่ได้ตั้งค่า Fabric ใน .env",
        )

    if fabric_can_query():
        try:
            rows = fabric_connector.fetch_schema_summary(top_schemas=30)
            if rows:
                return rows, "fabric", fabric_connector.settings.fabric_database
            logger.warning("Fabric schema scan returned no tables — trying Postgres mirror")
        except Exception as exc:
            logger.warning("Fabric schema scan failed, trying Postgres mirror: %s", exc)
            mark_fabric_unreachable()

    if pg_can_query():
        try:
            rows = pg_connector.fetch_schema_summary(top_schemas=30)
            if rows:
                return rows, "postgres", pg_connector.settings.pg_replica_db
            logger.warning("Postgres mirror schema scan returned no tables")
        except Exception as exc:
            logger.warning("Postgres mirror schema scan failed: %s", exc)
            mark_pg_unreachable()

    raise FabricConnectionError(
        "No live source available for schema scan (Fabric paused/unreachable, Postgres mirror unavailable)",
        "Fabric ไม่พร้อม (capacity pause/offline) และ Postgres mirror ใช้ไม่ได้ — สแกน schema ไม่ได้ในตอนนี้",
    )


SCAN_SOURCE_MSG_TH: dict[str, str] = {
    "postgres": "Fabric ไม่พร้อม — สแกนจาก Postgres mirror (WH_Silver) แทน",
    "cache": "Fabric และ Postgres mirror ไม่พร้อม — ใช้ผลสแกนล่าสุดจาก cache บนดิสก์",
}


async def scan_themes(*, use_llm: bool = True) -> dict[str, Any]:
    """Scan schema (Fabric preferred, Postgres mirror fallback) and propose top 3 themes.

    When neither live source is available, reuse cached themes from disk with a
    clear Thai warning instead of failing. Raises FabricConnectionError (-> 503)
    only when there is no live source AND no cache.
    """
    try:
        rows, source, database = await asyncio.to_thread(_fetch_scan_rows)
    except FabricConnectionError as exc:
        cached = load_cached_themes()
        if cached:
            logger.warning("Schema scan offline — reusing cached themes: %s", exc)
            cached = dict(cached)
            cached["source"] = "cache"
            cached["message"] = SCAN_SOURCE_MSG_TH["cache"]
            return cached
        raise

    clusters = cluster_schema_rows(rows)
    themes = _heuristic_themes(clusters, limit=3)

    if use_llm:
        themes = await _enrich_themes_with_llm(themes, rows)

    payload = {
        "scanned_at": _utc_now(),
        "database": database,
        "total_tables_scanned": len(rows),
        "themes": themes,
        "source": source,
        "message": SCAN_SOURCE_MSG_TH.get(source),
    }
    return save_cached_themes(payload)


def get_themes() -> dict[str, Any]:
    cached = load_cached_themes()
    if cached:
        return cached
    return {"scanned_at": None, "themes": [], "message": "ยังไม่ได้สแกน schema — กดสแกนก่อน"}
