"""Phase G2 — Metric Registry + SQL renderer."""

from __future__ import annotations

import pytest

from backend.app.services import metric_registry


@pytest.mark.asyncio
async def test_upsert_list_approve(temp_storage):
    entry = {
        "metric_key": "metric.test_revenue",
        "name_th": "ทดสอบ",
        "name_en": "Test",
        "status": "draft",
        "theme": "Saphanadb",
        "table": "SAPHANADB.CE1SATG_All_Cleaned",
        "time_column": "SourceMonth",
        "expression": "Revenue",
        "aggregation": "SUM",
        "dimensions": ["Customer"],
        "unit": "THB",
        "source": "owner_seed",
    }
    created = await metric_registry.upsert_metric(entry)
    assert created["status"] == "draft"
    approved = await metric_registry.approve_metric("metric.test_revenue")
    assert approved["status"] == "approved"
    items = await metric_registry.list_metrics(approved_only=True)
    assert any(m["metric_key"] == "metric.test_revenue" for m in items)


def test_render_metric_sql_fabric_and_postgres():
    entry = {
        "metric_key": "metric.gross_profit",
        "table": "SAPHANADB.CE1SATG_All_Cleaned",
        "time_column": "SourceMonth",
        "expression": "(Inter_Company + Revenue + Return_Revenue) - COGS_Actual",
        "aggregation": "SUM",
    }
    fab = metric_registry.render_metric_sql(entry, "fabric", months=["202601"], limit=5)
    assert "SELECT TOP 5" in fab
    assert "[SAPHANADB].[CE1SATG_All_Cleaned]" in fab
    assert "CAST([Revenue] AS DECIMAL(18,2))" in fab
    assert "[SourceMonth] IN ('202601')" in fab

    pg = metric_registry.render_metric_sql(entry, "postgres", months=["202601"], limit=5)
    assert "LIMIT 5" in pg
    assert '"SAPHANADB"."CE1SATG_All_Cleaned"' in pg
    assert 'CAST("Revenue" AS DECIMAL(18,2))' in pg


def test_render_rejects_derived():
    entry = {
        "metric_key": "metric.gp_pct",
        "table": "SAPHANADB.CE1SATG_All_Cleaned",
        "derived": {"kind": "ratio", "of": "a", "over": "b"},
        "expression": None,
    }
    with pytest.raises(ValueError, match="derived"):
        metric_registry.render_metric_sql(entry, "fabric")


def test_format_context_approved_only(temp_storage):
    import json
    from backend.app.services.metric_registry import _registry_path

    doc = {
        "version": "1.0",
        "metrics": [
            {
                "metric_key": "metric.ctx_ok",
                "name_th": "โอเค",
                "name_en": "OK",
                "status": "approved",
                "theme": "Saphanadb",
                "table": "T",
                "expression": "Revenue",
                "aggregation": "SUM",
            },
            {
                "metric_key": "metric.ctx_draft",
                "name_th": "ดราฟท์",
                "name_en": "Draft",
                "status": "draft",
                "theme": "Saphanadb",
                "expression": "Revenue",
            },
        ],
    }
    path = _registry_path()
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    ctx = metric_registry.format_metric_registry_context("Saphanadb")
    assert "metric.ctx_ok" in ctx
    assert "metric.ctx_draft" not in ctx


@pytest.mark.asyncio
async def test_metrics_api_list(client, temp_storage):
    await metric_registry.upsert_metric(
        {
            "metric_key": "metric.api_one",
            "name_th": "เอ",
            "name_en": "A",
            "status": "approved",
            "table": "SAPHANADB.CE1SATG_All_Cleaned",
            "expression": "Revenue",
            "aggregation": "SUM",
        }
    )
    resp = await client.get("/api/v1/metrics/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
