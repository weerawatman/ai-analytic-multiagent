"""Offline tests for contribution / Pareto / churn helpers."""

from __future__ import annotations

from pytest import approx

from backend.app.analytics.contribution import (
    concentration_hhi,
    contribution_breakdown,
    detect_churn_customers,
    detect_new_customers,
    mix_vs_rate_split,
    pareto_champions,
)


def test_contribution_top_driver():
    a = {"A": 100.0, "B": 50.0, "C": 10.0}
    b = {"A": 70.0, "B": 55.0, "C": 10.0}  # A drove the drop
    out = contribution_breakdown(a, b, top_k=2)
    assert out["total_delta"] == approx(-25.0)
    assert out["drivers"][0]["dim_value"] == "A"
    assert out["drivers"][0]["delta"] == approx(-30.0)
    assert abs(out["drivers"][0]["share_of_change"]) > 0.5


def test_mix_vs_rate_split():
    vol_a = {"X": 100.0, "Y": 100.0}
    vol_b = {"X": 150.0, "Y": 100.0}
    rate_a = {"X": 0.2, "Y": 0.2}
    rate_b = {"X": 0.1, "Y": 0.2}  # X margin drop
    out = mix_vs_rate_split(vol_a, vol_b, rate_a, rate_b, top_k=2)
    x = next(d for d in out["drivers"] if d["dim_value"] == "X")
    assert x["rate_effect"] < 0
    assert x["mix_effect"] > 0  # volume up at old rate


def test_pareto_and_hhi():
    vals = {f"c{i}": float(100 - i) for i in range(20)}
    vals["c0"] = 500.0
    p = pareto_champions(vals, top_n=5, pareto_pct=0.8)
    assert p["champions"][0]["dim_value"] == "c0"
    assert p["pareto_count"] >= 1
    h = concentration_hhi(vals)
    assert 0 < h["hhi"] <= 1.0


def test_churn_and_new_customers():
    lookback = ["202401", "202402", "202403", "202404", "202405", "202406"]
    recent = ["202407", "202408"]
    data = {
        "old_loyal": {m: 10.0 for m in lookback},  # churn — zero recent
        "still_here": {**{m: 10.0 for m in lookback}, "202407": 5.0, "202408": 5.0},
        "brand_new": {"202407": 20.0, "202408": 15.0},
    }
    churned = detect_churn_customers(
        data, lookback_months=lookback, recent_months=recent, min_active_months=2
    )
    assert any(c["dim_value"] == "old_loyal" for c in churned)
    assert not any(c["dim_value"] == "still_here" for c in churned)

    newcomers = detect_new_customers(
        data, lookback_months=lookback, recent_months=recent
    )
    assert any(c["dim_value"] == "brand_new" for c in newcomers)
