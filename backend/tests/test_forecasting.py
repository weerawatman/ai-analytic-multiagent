"""Offline tests for forecasting baselines."""

from __future__ import annotations

from backend.app.analytics.forecasting import (
    forecast_baseline,
    forecast_residual_flags,
    has_ets,
    seasonal_naive_forecast,
)


def test_seasonal_naive_repeats_prior_year():
    # 24 months; last 12 mirror first 12 with noise-free seasonality
    values = [float(10 + (i % 12)) for i in range(24)]
    fc = seasonal_naive_forecast(values, horizon=3, m=12)
    assert fc["method"] == "seasonal_naive"
    assert len(fc["point"]) == 3
    # Next point should equal value at index 12 (same season as index 0 of next year)
    assert fc["point"][0] == values[12]


def test_forecast_baseline_always_returns():
    values = [float(i) for i in range(30)]
    out = forecast_baseline(values, horizon=2, m=12, prefer_ets=True)
    assert out["method"] in {"seasonal_naive", "ets"}
    assert len(out["point"]) == 2
    assert len(out["lower"]) == 2
    assert len(out["upper"]) == 2


def test_forecast_residual_flags_spike():
    values = [100.0] * 24
    values[18] = 10.0  # break vs seasonal naive
    periods = [f"p{i}" for i in range(24)]
    flags = forecast_residual_flags(values, periods=periods, m=12)
    assert any(f["period"] == "p18" and f["direction"] == "down" for f in flags)


def test_has_ets_is_bool():
    assert isinstance(has_ets(), bool)
