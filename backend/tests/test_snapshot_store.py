"""Snapshot store + refresh service tests (offline / mocked SQL)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services import snapshot_refresh_service, snapshot_store


@pytest.fixture()
def analytics_db(tmp_path: Path) -> Path:
    db = tmp_path / "analytics.db"
    snapshot_store.init_analytics_db(db)
    return db


def test_upsert_and_get_series(analytics_db: Path):
    n = snapshot_store.upsert_snapshots(
        [
            {
                "metric_key": "metric.revenue",
                "period": "202401",
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 100.0,
                "row_count": 1,
                "source": "postgres",
            },
            {
                "metric_key": "metric.revenue",
                "period": "202402",
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 110.0,
                "row_count": 1,
                "source": "postgres",
            },
        ],
        db_path=analytics_db,
    )
    assert n == 2
    series = snapshot_store.get_series("metric.revenue", db_path=analytics_db)
    assert [r["period"] for r in series] == ["202401", "202402"]
    assert series[1]["value"] == 110.0

    # Upsert overwrite
    snapshot_store.upsert_snapshots(
        [
            {
                "metric_key": "metric.revenue",
                "period": "202402",
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": 115.0,
                "source": "postgres",
            }
        ],
        db_path=analytics_db,
    )
    series = snapshot_store.get_series("metric.revenue", db_path=analytics_db)
    assert series[1]["value"] == 115.0


def test_snapshot_run_lifecycle(analytics_db: Path):
    run_id = snapshot_store.start_snapshot_run(
        source="postgres", months_window="backfill:202201-202412", db_path=analytics_db
    )
    snapshot_store.finish_snapshot_run(
        run_id, status="done", metrics_refreshed=3, db_path=analytics_db
    )
    latest = snapshot_store.latest_run(db_path=analytics_db)
    assert latest is not None
    assert latest["id"] == run_id
    assert latest["status"] == "done"
    assert latest["metrics_refreshed"] == 3
    status = snapshot_store.snapshot_status(db_path=analytics_db)
    assert status["latest_run"]["id"] == run_id


def test_product_cap_rolls_other():
    rows = [
        {
            "metric_key": "metric.revenue",
            "period": "202401",
            "dim_name": "Product_Number",
            "dim_value": f"P{i}",
            "value": float(1000 - i),
            "row_count": 1,
            "source": "postgres",
        }
        for i in range(600)
    ]
    capped = snapshot_refresh_service._cap_product_rows(rows, top_n=500)
    values = {r["dim_value"] for r in capped}
    assert "__other__" in values
    assert len([r for r in capped if r["dim_value"] != "__other__"]) == 500
    other = next(r for r in capped if r["dim_value"] == "__other__")
    assert other["value"] > 0


def test_month_window_helpers():
    months = snapshot_refresh_service.month_window_ending("202406", 3)
    assert months == ["202404", "202405", "202406"]
    back = snapshot_refresh_service.month_window_ending("202401", 36)
    assert len(back) == 36
    assert back[-1] == "202401"
    assert back[0] == "202102"


@pytest.mark.asyncio
async def test_resolve_refresh_months_auto(analytics_db: Path):
    months, label = await snapshot_refresh_service.resolve_refresh_months(
        mode="auto",
        end_month="202406",
        get_latest_run=lambda: None,
    )
    assert len(months) == 36
    assert label.startswith("backfill:")

    months2, label2 = await snapshot_refresh_service.resolve_refresh_months(
        mode="auto",
        end_month="202406",
        get_latest_run=lambda: {"status": "done"},
    )
    assert len(months2) == 3
    assert label2.startswith("incremental:")


@pytest.mark.asyncio
async def test_refresh_snapshots_mocked(analytics_db: Path, monkeypatch: pytest.MonkeyPatch):
    entry = {
        "metric_key": "metric.revenue",
        "expression": "Revenue",
        "aggregation": "SUM",
        "table": "SAPHANADB.CE1SATG_All_Cleaned",
        "time_column": "SourceMonth",
        "dimensions": ["Customer", "Product_Number"],
        "status": "approved",
        "derived": None,
    }

    async def _list_metrics(**_kwargs):
        return [entry]

    monkeypatch.setattr(
        "backend.app.services.snapshot_refresh_service.list_metrics", _list_metrics
    )

    def _fake_sql(sql: str, *, mode="explore", max_rows=None, source="postgres"):
        # Totals vs dim based on SELECT shape
        if "AS dim_value" in sql or 'AS "dim_value"' in sql or "dim_value" in sql.lower():
            rows = [
                {"period": "202404", "dim_value": "A", "metric_value": 10.0},
                {"period": "202405", "dim_value": "A", "metric_value": 12.0},
                {"period": "202406", "dim_value": "B", "metric_value": 5.0},
            ]
        else:
            rows = [
                {"period": "202404", "metric_value": 100.0},
                {"period": "202405", "metric_value": 110.0},
                {"period": "202406", "metric_value": 120.0},
            ]
        return {"rows": rows, "source": source}

    result = await snapshot_refresh_service.refresh_snapshots(
        mode="incremental",
        end_month="202406",
        run_sql_fn=_fake_sql,
        get_source_fn=lambda: "postgres",
        db_path=analytics_db,
    )
    assert result["status"] == "done"
    assert result["metrics_refreshed"] == 1
    assert result["source"] == "postgres"
    series = snapshot_store.get_series("metric.revenue", db_path=analytics_db)
    assert len(series) == 3
    assert series[-1]["value"] == 120.0


def test_summarize_detectors_for_theme(analytics_db: Path):
    # Build a crash series
    rows = []
    for i, m in enumerate(range(1, 13)):
        period = f"2024{m:02d}"
        val = 100.0 if m != 9 else 20.0
        rows.append(
            {
                "metric_key": "metric.revenue",
                "period": period,
                "dim_name": "__total__",
                "dim_value": "__total__",
                "value": val,
                "source": "postgres",
            }
        )
    snapshot_store.upsert_snapshots(rows, db_path=analytics_db)
    text = snapshot_refresh_service.summarize_detectors_for_theme(
        "sales", metric_keys=["metric.revenue"], db_path=analytics_db
    )
    assert "metric.revenue" in text
    assert "trend" in text.lower() or "anomal" in text.lower()


def test_inv7_no_app_db_string():
    """Guardrail smoke: analytics services must not mention the chat DB filename."""
    from pathlib import Path as P

    root = P(__file__).resolve().parents[1] / "app" / "services"
    banned = "app." + "db"  # avoid literal in this file confusing greps
    for name in ("snapshot_store.py", "snapshot_refresh_service.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert banned not in text
