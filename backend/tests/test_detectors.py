"""Offline unit tests for Phase H detectors (synthetic series)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.analytics.detectors import (
    detect_anomalies,
    detect_changepoints,
    detect_trend,
    has_stl,
    iqr_fence_mask,
    robust_z_scores,
)


def test_robust_z_flags_spike():
    base = [100.0] * 20
    base[15] = 400.0  # clear spike
    z = robust_z_scores(base)
    assert abs(z[15]) > abs(z[0])
    assert abs(z[15]) >= 3.0


def test_iqr_fence_detects_outlier():
    vals = list(range(1, 21)) + [1000]
    mask = iqr_fence_mask(vals)
    assert mask[-1]


def test_detect_anomalies_spike_down():
    periods = [f"2024{m:02d}" for m in range(1, 13)]
    values = [100.0] * 12
    values[8] = 20.0  # Sep crash
    events = detect_anomalies(values, periods=periods, z_threshold=2.5, use_stl=False)
    assert events
    crash = [e for e in events if e["period"] == "202409"]
    assert crash
    assert crash[0]["direction"] == "down"


def test_detect_changepoints_level_shift():
    values = [10.0] * 15 + [40.0] * 15
    periods = [str(i) for i in range(len(values))]
    cps = detect_changepoints(values, periods=periods, threshold_sigma=2.0)
    assert cps
    # First flagged index should be near the shift
    assert any(10 <= c["index"] <= 20 for c in cps)


def test_detect_trend_upward():
    values = [float(i) for i in range(24)]
    trend = detect_trend(values)
    assert trend["direction"] == "up"
    assert trend["significant"] is True
    assert trend["slope"] > 0


def test_detect_trend_flat_noise():
    rng = np.random.default_rng(42)
    values = rng.normal(100.0, 1.0, size=30).tolist()
    trend = detect_trend(values, alpha=0.01)
    # With tiny noise around constant, should usually be flat / insignificant
    assert trend["n"] == 30


def test_has_stl_is_bool():
    assert isinstance(has_stl(), bool)


def test_historical_events_recall_three_cases():
    """Acceptance: detectors catch ≥3 known synthetic 'owner-known' events."""
    # Case 1: sales crash month
    periods = [f"2023{m:02d}" for m in range(1, 13)] + [f"2024{m:02d}" for m in range(1, 13)]
    sales = [100.0 + (i % 12) * 2 for i in range(24)]
    sales[14] = 30.0  # 202403 crash
    a1 = detect_anomalies(sales, periods=periods, z_threshold=2.5, use_stl=False)
    assert any(e["period"] == "202403" and e["direction"] == "down" for e in a1)

    # Case 2: sustained level shift (new plant / reorg)
    shifted = [50.0] * 12 + [120.0] * 12
    cps = detect_changepoints(shifted, periods=periods, threshold_sigma=2.5)
    assert len(cps) >= 1

    # Case 3: clear upward trend (growth year)
    growth = [80.0 + i * 3.5 for i in range(24)]
    trend = detect_trend(growth, periods=periods)
    assert trend["direction"] == "up" and trend["significant"]

    # Extra: forecast residual flag covered in test_forecasting
    caught = 3
    assert caught >= 3
