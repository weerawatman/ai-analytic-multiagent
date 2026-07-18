"""Refresh metric snapshots from Fabric/Postgres via Metric Registry (Phase H).

Scheduled / on-demand path: SQL is rendered deterministically with
``render_metric_sql`` — never via LLM (INV-3). Execution goes through
``fabric_sql.run_sql`` so sql_guard + row-count guard + provenance apply (INV-9).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from backend.app.core.logger import logger
from backend.app.services import snapshot_store
from backend.app.services.fabric_sql import get_active_sql_source, run_sql
from backend.app.services.metric_registry import list_metrics, render_metric_sql

# Locked snapshot grain (roadmap §3)
DEFAULT_DIMENSIONS = (
    "Customer",
    "Product_Number",
    "Profit_Center",
    "Sales_Organization",
    "Material_Group_MATKL",
)
PRODUCT_DIM = "Product_Number"
PRODUCT_TOP_N = 500
BACKFILL_MONTHS = 36
INCREMENTAL_MONTHS = 3

# Aggregated GROUP BY results can be larger than chat max_rows; still under
# fabric_row_count_threshold (50k) for 1-D slices.
_SNAPSHOT_MAX_ROWS = 20000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _yyyymm_shift(yyyymm: str, delta: int) -> str:
    y = int(yyyymm[:4])
    m = int(yyyymm[4:6])
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12:04d}{(idx % 12) + 1:02d}"


def month_window_ending(end: str, n: int) -> list[str]:
    """Return ``n`` YYYYMM months ending at ``end`` (inclusive), ascending."""
    months = [_yyyymm_shift(end, -i) for i in range(n - 1, -1, -1)]
    return months


def default_end_month() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}{now.month:02d}"


def _parse_value(row: dict[str, Any]) -> float | None:
    for key in ("metric_value", "METRIC_VALUE", "value", "VALUE"):
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                return None
    return None


def _parse_period(row: dict[str, Any]) -> str | None:
    for key in ("period", "PERIOD", "SourceMonth", "SOURCEMONTH"):
        if key in row and row[key] is not None:
            text = str(row[key]).strip()
            if text:
                return text
    return None


def _parse_dim(row: dict[str, Any]) -> str | None:
    for key in ("dim_value", "DIM_VALUE"):
        if key in row and row[key] is not None:
            return str(row[key])
    return None


def _cap_product_rows(
    rows: list[dict[str, Any]],
    *,
    top_n: int = PRODUCT_TOP_N,
) -> list[dict[str, Any]]:
    """Keep top-N Product_Number by |value| per period; roll rest into __other__."""
    by_period: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_period.setdefault(r["period"], []).append(r)

    out: list[dict[str, Any]] = []
    for period, items in by_period.items():
        ranked = sorted(items, key=lambda x: abs(float(x.get("value") or 0.0)), reverse=True)
        keep = ranked[:top_n]
        rest = ranked[top_n:]
        out.extend(keep)
        if rest:
            out.append(
                {
                    "metric_key": rest[0]["metric_key"],
                    "period": period,
                    "dim_name": PRODUCT_DIM,
                    "dim_value": "__other__",
                    "value": float(sum(float(x.get("value") or 0.0) for x in rest)),
                    "row_count": sum(int(x.get("row_count") or 0) for x in rest),
                    "source": rest[0].get("source") or "",
                    "refreshed_at": rest[0].get("refreshed_at") or _utc_now(),
                }
            )
    return out


def _rows_from_sql_result(
    result: dict[str, Any],
    *,
    metric_key: str,
    dim_name: str,
    source: str,
) -> list[dict[str, Any]]:
    now = _utc_now()
    out: list[dict[str, Any]] = []
    for raw in result.get("rows") or []:
        period = _parse_period(raw)
        value = _parse_value(raw)
        if period is None:
            continue
        if dim_name == "__total__":
            dim_value = "__total__"
        else:
            dim_value = _parse_dim(raw)
            if dim_value is None:
                continue
        out.append(
            {
                "metric_key": metric_key,
                "period": period,
                "dim_name": dim_name,
                "dim_value": dim_value,
                "value": value,
                "row_count": 1,
                "source": result.get("source") or source,
                "refreshed_at": now,
            }
        )
    return out


async def resolve_refresh_months(
    *,
    mode: str = "auto",
    end_month: str | None = None,
    get_latest_run: Callable[..., dict[str, Any] | None] | None = None,
) -> tuple[list[str], str]:
    """Choose backfill (36) vs incremental (3) month window.

    ``mode``: auto | backfill | incremental
    Returns (months ascending, window_label).
    """
    end = end_month or default_end_month()
    latest_fn = get_latest_run or snapshot_store.latest_run
    if mode == "backfill":
        months = month_window_ending(end, BACKFILL_MONTHS)
        return months, f"backfill:{months[0]}-{months[-1]}"
    if mode == "incremental":
        months = month_window_ending(end, INCREMENTAL_MONTHS)
        return months, f"incremental:{months[0]}-{months[-1]}"

    # auto: first successful run → incremental; else backfill
    run = latest_fn()
    if run and run.get("status") == "done":
        months = month_window_ending(end, INCREMENTAL_MONTHS)
        return months, f"incremental:{months[0]}-{months[-1]}"
    months = month_window_ending(end, BACKFILL_MONTHS)
    return months, f"backfill:{months[0]}-{months[-1]}"


async def refresh_snapshots(
    *,
    mode: str = "auto",
    end_month: str | None = None,
    metric_keys: list[str] | None = None,
    dimensions: list[str] | None = None,
    progress_cb: Callable[[str], None] | None = None,
    run_sql_fn: Callable[..., dict[str, Any]] | None = None,
    get_source_fn: Callable[[], str] | None = None,
    db_path: Any = None,
) -> dict[str, Any]:
    """Refresh snapshots for approved non-derived metrics.

    ``progress_cb(step_note)`` is optional (job_runner wires job_store notes).
    """
    snapshot_store.init_analytics_db(db_path)
    source = (get_source_fn or get_active_sql_source)()
    if source == "offline":
        raise RuntimeError("No SQL source available (offline) — cannot refresh snapshots")

    months, window_label = await resolve_refresh_months(mode=mode, end_month=end_month)
    run_id = snapshot_store.start_snapshot_run(
        source=source, months_window=window_label, db_path=db_path
    )
    sql_runner = run_sql_fn or run_sql
    dims = list(dimensions) if dimensions is not None else list(DEFAULT_DIMENSIONS)
    metrics_done = 0
    errors: list[str] = []

    try:
        entries = await list_metrics(approved_only=True)
        entries = [
            e
            for e in entries
            if not e.get("derived") and e.get("expression")
            and (metric_keys is None or e.get("metric_key") in metric_keys)
        ]
        if not entries:
            raise RuntimeError("No approved base metrics to refresh")

        for entry in entries:
            key = entry["metric_key"]
            if progress_cb:
                progress_cb(f"refresh {key} (__total__)")
            try:
                # Totals
                sql = render_metric_sql(
                    entry, source, months=months, dimension=None, limit=None
                )
                result = sql_runner(sql, mode="explore", max_rows=_SNAPSHOT_MAX_ROWS, source=source)
                rows = _rows_from_sql_result(
                    result, metric_key=key, dim_name="__total__", source=source
                )
                snapshot_store.upsert_snapshots(rows, db_path=db_path)

                declared = entry.get("dimensions") or dims
                for dim in dims:
                    if dim not in declared:
                        continue
                    if progress_cb:
                        progress_cb(f"refresh {key} ({dim})")
                    sql = render_metric_sql(
                        entry, source, months=months, dimension=dim, limit=None
                    )
                    result = sql_runner(
                        sql, mode="explore", max_rows=_SNAPSHOT_MAX_ROWS, source=source
                    )
                    dim_rows = _rows_from_sql_result(
                        result, metric_key=key, dim_name=dim, source=source
                    )
                    if dim == PRODUCT_DIM:
                        dim_rows = _cap_product_rows(dim_rows)
                    snapshot_store.upsert_snapshots(dim_rows, db_path=db_path)

                metrics_done += 1
            except Exception as exc:
                logger.exception("Snapshot refresh failed for %s", key)
                errors.append(f"{key}: {type(exc).__name__}")

        status = "done" if metrics_done else "failed"
        err_text = "; ".join(errors) if errors else None
        if metrics_done and errors:
            status = "done"  # partial success still usable
        snapshot_store.finish_snapshot_run(
            run_id,
            status=status if metrics_done else "failed",
            metrics_refreshed=metrics_done,
            error=err_text,
            db_path=db_path,
        )
        return {
            "run_id": run_id,
            "status": status if metrics_done else "failed",
            "source": source,
            "months_window": window_label,
            "metrics_refreshed": metrics_done,
            "errors": errors,
        }
    except Exception as exc:
        snapshot_store.finish_snapshot_run(
            run_id,
            status="failed",
            metrics_refreshed=metrics_done,
            error=f"{type(exc).__name__}: {exc}",
            db_path=db_path,
        )
        raise


def summarize_detectors_for_theme(
    theme: str | None = None,
    *,
    metric_keys: list[str] | None = None,
    db_path: Any = None,
) -> str:
    """Build a short Thai/English analytics_context block for the DS agent.

    Reads ``__total__`` series from snapshots and runs pure detectors offline.
    """
    from backend.app.analytics.detectors import detect_anomalies, detect_changepoints, detect_trend

    # Lazy import to keep refresh path free of analytics if unused
    keys = metric_keys
    if keys is None:
        # Best-effort: pick metrics present in store
        status = snapshot_store.snapshot_status(db_path)
        if status["metric_count"] == 0:
            return ""
        # Sample a few series via distinct query
        with snapshot_store.get_analytics_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT metric_key FROM metric_snapshots
                WHERE dim_name = '__total__'
                ORDER BY metric_key LIMIT 8
                """
            ).fetchall()
        keys = [r[0] for r in rows]

    lines = ["## Analytics context (computed detectors — not LLM guesses)"]
    if theme:
        lines.append(f"Theme filter hint: {theme}")

    for key in keys[:6]:
        series = snapshot_store.get_series(key, db_path=db_path)
        if len(series) < 4:
            continue
        periods = [r["period"] for r in series]
        values = [float(r["value"] or 0.0) for r in series]
        anomalies = detect_anomalies(values, periods=periods, use_stl=False)
        cps = detect_changepoints(values, periods=periods)
        trend = detect_trend(values, periods=periods)
        lines.append(f"### {key}")
        lines.append(
            f"- trend: {trend['direction']} (slope={trend['slope']:.4g}, "
            f"MK p={trend['mann_kendall_p']:.3f}, significant={trend['significant']})"
        )
        if anomalies:
            top = anomalies[-3:]
            desc = ", ".join(f"{a['period']}({a['direction']}/{a['methods'][0]})" for a in top)
            lines.append(f"- anomalies (latest): {desc}")
        if cps:
            top_cp = cps[-2:]
            desc = ", ".join(f"{c['period']}({c['direction']})" for c in top_cp)
            lines.append(f"- changepoints: {desc}")

    if len(lines) <= 2:
        return ""
    return "\n".join(lines)
