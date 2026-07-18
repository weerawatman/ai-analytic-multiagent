"""Contribution / mix analysis — GA Insights-style 1-D driver breakdown."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def contribution_breakdown(
    period_a: dict[str, float],
    period_b: dict[str, float],
    *,
    top_k: int = 10,
    total_a: float | None = None,
    total_b: float | None = None,
) -> dict[str, Any]:
    """Break Δ of a metric between two periods by dimension value.

    ``period_a`` / ``period_b`` map dim_value → metric value for one period each.
    Returns top-k drivers by |Δ| with share-of-change.
    """
    keys = set(period_a) | set(period_b)
    rows: list[dict[str, Any]] = []
    for k in keys:
        a = float(period_a.get(k, 0.0))
        b = float(period_b.get(k, 0.0))
        delta = b - a
        rows.append({"dim_value": k, "value_a": a, "value_b": b, "delta": delta})

    sum_a = float(sum(r["value_a"] for r in rows)) if total_a is None else float(total_a)
    sum_b = float(sum(r["value_b"] for r in rows)) if total_b is None else float(total_b)
    total_delta = sum_b - sum_a
    denom = abs(total_delta) if abs(total_delta) > 1e-12 else 1.0

    for r in rows:
        r["share_of_change"] = float(r["delta"] / denom)

    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    top = rows[:top_k]
    other = rows[top_k:]
    other_payload = None
    if other:
        other_payload = {
            "dim_value": "__other__",
            "value_a": float(sum(r["value_a"] for r in other)),
            "value_b": float(sum(r["value_b"] for r in other)),
            "delta": float(sum(r["delta"] for r in other)),
            "share_of_change": float(sum(r["delta"] for r in other) / denom),
            "n_members": len(other),
        }
    return {
        "total_a": sum_a,
        "total_b": sum_b,
        "total_delta": total_delta,
        "drivers": top,
        "other": other_payload,
        "n_dims": len(rows),
    }


def mix_vs_rate_split(
    volume_a: dict[str, float],
    volume_b: dict[str, float],
    rate_a: dict[str, float],
    rate_b: dict[str, float],
    *,
    top_k: int = 10,
) -> dict[str, Any]:
    """Decompose ratio-metric Δ into mix (volume) vs rate effects.

    For each dim: contribution ≈ rate_a * Δvolume + volume_b * Δrate
    (Laspeyres-style mix + Paasche-style rate).
    """
    keys = set(volume_a) | set(volume_b) | set(rate_a) | set(rate_b)
    rows: list[dict[str, Any]] = []
    for k in keys:
        va, vb = float(volume_a.get(k, 0.0)), float(volume_b.get(k, 0.0))
        ra, rb = float(rate_a.get(k, 0.0)), float(rate_b.get(k, 0.0))
        mix_effect = ra * (vb - va)
        rate_effect = vb * (rb - ra)
        rows.append(
            {
                "dim_value": k,
                "mix_effect": mix_effect,
                "rate_effect": rate_effect,
                "total_effect": mix_effect + rate_effect,
                "volume_a": va,
                "volume_b": vb,
                "rate_a": ra,
                "rate_b": rb,
            }
        )
    rows.sort(key=lambda r: abs(r["total_effect"]), reverse=True)
    return {
        "drivers": rows[:top_k],
        "mix_total": float(sum(r["mix_effect"] for r in rows)),
        "rate_total": float(sum(r["rate_effect"] for r in rows)),
        "n_dims": len(rows),
    }


def pareto_champions(
    values_by_dim: dict[str, float],
    *,
    top_n: int = 10,
    pareto_pct: float = 0.8,
) -> dict[str, Any]:
    """Top-N champions + how many dims cover ``pareto_pct`` of total."""
    items = sorted(
        ((k, float(v)) for k, v in values_by_dim.items() if float(v) > 0),
        key=lambda kv: kv[1],
        reverse=True,
    )
    total = float(sum(v for _, v in items)) or 1.0
    cum = 0.0
    pareto_count = 0
    for i, (_, v) in enumerate(items, start=1):
        cum += v
        if cum / total >= pareto_pct:
            pareto_count = i
            break
    else:
        pareto_count = len(items)

    champions = [
        {
            "dim_value": k,
            "value": v,
            "share": v / total,
            "rank": i,
        }
        for i, (k, v) in enumerate(items[:top_n], start=1)
    ]
    return {
        "total": total if items else 0.0,
        "champions": champions,
        "pareto_count": pareto_count,
        "pareto_pct": pareto_pct,
        "n_positive": len(items),
    }


def concentration_hhi(values_by_dim: dict[str, float]) -> dict[str, Any]:
    """Herfindahl-Hirschman Index (0–1 share-squared sum)."""
    vals = np.array([float(v) for v in values_by_dim.values() if float(v) > 0], dtype=float)
    if len(vals) == 0:
        return {"hhi": 0.0, "n": 0, "interpretation": "empty"}
    shares = vals / vals.sum()
    hhi = float(np.sum(shares**2))
    if hhi < 0.15:
        label = "unconcentrated"
    elif hhi < 0.25:
        label = "moderate"
    else:
        label = "high"
    return {"hhi": hhi, "n": int(len(vals)), "interpretation": label}


def detect_churn_customers(
    monthly_by_customer: dict[str, dict[str, float]],
    *,
    lookback_months: list[str],
    recent_months: list[str],
    min_active_months: int = 2,
) -> list[dict[str, Any]]:
    """Customers with revenue in ≥``min_active_months`` of lookback, zero in recent.

    ``monthly_by_customer``: customer → {period → revenue}.
    """
    churned: list[dict[str, Any]] = []
    for cust, series in monthly_by_customer.items():
        active = sum(1 for m in lookback_months if float(series.get(m, 0.0)) > 0)
        recent_sum = sum(float(series.get(m, 0.0)) for m in recent_months)
        if active >= min_active_months and recent_sum == 0.0:
            prior = sum(float(series.get(m, 0.0)) for m in lookback_months)
            churned.append(
                {
                    "dim_value": cust,
                    "active_months_prior": active,
                    "prior_revenue": prior,
                    "recent_revenue": 0.0,
                }
            )
    churned.sort(key=lambda r: r["prior_revenue"], reverse=True)
    return churned


def detect_new_customers(
    monthly_by_customer: dict[str, dict[str, float]],
    *,
    lookback_months: list[str],
    recent_months: list[str],
) -> list[dict[str, Any]]:
    """Customers with zero revenue in lookback and positive in recent window."""
    newcomers: list[dict[str, Any]] = []
    for cust, series in monthly_by_customer.items():
        prior = sum(float(series.get(m, 0.0)) for m in lookback_months)
        recent = sum(float(series.get(m, 0.0)) for m in recent_months)
        if prior == 0.0 and recent > 0.0:
            newcomers.append(
                {
                    "dim_value": cust,
                    "prior_revenue": 0.0,
                    "recent_revenue": recent,
                }
            )
    newcomers.sort(key=lambda r: r["recent_revenue"], reverse=True)
    return newcomers


def series_to_dim_map(df: pd.DataFrame, *, dim_col: str, value_col: str) -> dict[str, float]:
    """Helper: DataFrame → {dim_value: value} (sums duplicates)."""
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        k = str(row[dim_col])
        out[k] = out.get(k, 0.0) + float(row[value_col])
    return out
