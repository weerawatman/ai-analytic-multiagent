"""Anomaly, changepoint, and trend detectors — pure numpy/pandas/scipy.

STL residual anomaly is optional when statsmodels is importable.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Optional STL (statsmodels) — import-guarded per roadmap §3 / risk #1
# ---------------------------------------------------------------------------
try:
    from statsmodels.tsa.seasonal import STL as _STL  # type: ignore

    _HAS_STL = True
except Exception:  # pragma: no cover - optional dep
    _STL = None  # type: ignore
    _HAS_STL = False


def _to_series(values: list[float] | np.ndarray | pd.Series) -> pd.Series:
    if isinstance(values, pd.Series):
        s = values.astype(float)
    else:
        s = pd.Series(np.asarray(values, dtype=float))
    return s.reset_index(drop=True)


def _mad(x: np.ndarray) -> float:
    med = float(np.median(x))
    return float(np.median(np.abs(x - med)))


def robust_z_scores(values: list[float] | np.ndarray | pd.Series) -> np.ndarray:
    """Median/MAD robust z-score (scaled by 1.4826).

    When MAD is ~0 (e.g. many identical values with one spike), fall back to
    mean absolute deviation, then sample std — never silently zero-out spikes.
    """
    x = _to_series(values).to_numpy(dtype=float)
    med = float(np.median(x))
    mad = _mad(x)
    scale = 1.4826 * mad
    if scale < 1e-12:
        # Fallback: mean absolute deviation from median
        scale = float(np.mean(np.abs(x - med)))
    if scale < 1e-12:
        scale = float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
    if scale < 1e-12:
        return np.zeros_like(x)
    return (x - med) / scale


def iqr_fence_mask(
    values: list[float] | np.ndarray | pd.Series, *, k: float = 1.5
) -> np.ndarray:
    """Boolean mask: True where value is outside Tukey's IQR fence."""
    x = _to_series(values).to_numpy(dtype=float)
    q1, q3 = np.percentile(x, [25, 75])
    iqr = float(q3 - q1)
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return (x < lo) | (x > hi)


def stl_residual_z(
    values: list[float] | np.ndarray | pd.Series, *, period: int = 12
) -> np.ndarray | None:
    """Z-score of STL residuals if statsmodels available and series long enough."""
    if not _HAS_STL or _STL is None:
        return None
    s = _to_series(values)
    if len(s) < max(2 * period, 24):
        return None
    try:
        res = _STL(s, period=period, robust=True).fit()
        resid = np.asarray(res.resid, dtype=float)
        mu = float(np.nanmean(resid))
        sd = float(np.nanstd(resid, ddof=1))
        if sd < 1e-12:
            return np.zeros_like(resid)
        return (resid - mu) / sd
    except Exception:
        return None


def detect_anomalies(
    values: list[float] | np.ndarray | pd.Series,
    *,
    periods: list[str] | None = None,
    z_threshold: float = 3.0,
    iqr_k: float = 1.5,
    use_stl: bool = True,
    stl_period: int = 12,
) -> list[dict[str, Any]]:
    """Detect anomalies via robust z-score and/or IQR fence (+ optional STL).

    Returns a list of event dicts with index, period (if given), value,
    methods that fired, and scores.
    """
    s = _to_series(values)
    n = len(s)
    if n == 0:
        return []
    periods = periods or [str(i) for i in range(n)]
    if len(periods) != n:
        raise ValueError("periods length must match values")

    rz = robust_z_scores(s)
    iqr_mask = iqr_fence_mask(s, k=iqr_k)
    stl_z = stl_residual_z(s, period=stl_period) if use_stl else None

    events: list[dict[str, Any]] = []
    for i in range(n):
        methods: list[str] = []
        scores: dict[str, float] = {"robust_z": float(rz[i])}
        if abs(rz[i]) >= z_threshold:
            methods.append("robust_z")
        if iqr_mask[i]:
            methods.append("iqr")
        if stl_z is not None:
            scores["stl_z"] = float(stl_z[i])
            if abs(stl_z[i]) >= z_threshold:
                methods.append("stl_residual")
        if not methods:
            continue
        events.append(
            {
                "index": i,
                "period": periods[i],
                "value": float(s.iloc[i]),
                "direction": "up" if s.iloc[i] > float(np.median(s)) else "down",
                "methods": methods,
                "scores": scores,
                "significance": float(max(abs(rz[i]), abs(scores.get("stl_z", 0.0)))),
            }
        )
    return events


def detect_changepoints(
    values: list[float] | np.ndarray | pd.Series,
    *,
    periods: list[str] | None = None,
    threshold_sigma: float = 3.0,
) -> list[dict[str, Any]]:
    """Offline CUSUM mean-shift detection (numpy only).

    For a single level shift, ``S_k = sum_{i<=k}(x_i - mean(x))`` peaks at the
    change index. We report local extrema of |S| that exceed
    ``threshold_sigma * std * sqrt(n)`` (scaled random-walk bound), plus any
    secondary peaks after resetting the cumulative sum.
    """
    s = _to_series(values)
    n = len(s)
    if n < 4:
        return []
    periods = periods or [str(i) for i in range(n)]
    x = s.to_numpy(dtype=float)
    mu = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    if sd < 1e-12:
        return []
    cusum = np.cumsum(x - mu)
    # Bound similar to Brownian bridge scale
    thr = threshold_sigma * sd * np.sqrt(n)
    # Primary changepoint = argmax |S|
    peak_idx = int(np.argmax(np.abs(cusum)))
    events: list[dict[str, Any]] = []
    if abs(cusum[peak_idx]) >= thr * 0.5:  # half-threshold for primary peak
        # Prefer the first index of the new regime (peak+1 when possible)
        idx = min(peak_idx + 1, n - 1) if peak_idx + 1 < n else peak_idx
        mean_before = float(np.mean(x[:idx])) if idx > 0 else float(x[0])
        mean_after = float(np.mean(x[idx:])) if idx < n else float(x[-1])
        direction = "up" if mean_after > mean_before else "down"
        events.append(
            {
                "index": idx,
                "period": periods[idx],
                "value": float(x[idx]),
                "cusum": float(cusum[peak_idx]),
                "threshold": float(thr),
                "direction": direction,
                "significance": float(abs(cusum[peak_idx]) / (thr + 1e-12)),
            }
        )
    # Also emit contiguous-run crossings of full threshold (secondary shifts)
    crossed = np.abs(cusum) > thr
    prev = False
    for i, flag in enumerate(crossed):
        if flag and not prev:
            if events and abs(i - events[0]["index"]) <= 2:
                prev = True
                continue
            events.append(
                {
                    "index": i,
                    "period": periods[i],
                    "value": float(x[i]),
                    "cusum": float(cusum[i]),
                    "threshold": float(thr),
                    "direction": "up" if cusum[i] > 0 else "down",
                    "significance": float(abs(cusum[i]) / (thr + 1e-12)),
                }
            )
        prev = bool(flag)
    return events


def detect_trend(
    values: list[float] | np.ndarray | pd.Series,
    *,
    periods: list[str] | None = None,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Theil-Sen slope + Mann-Kendall significance (scipy)."""
    s = _to_series(values)
    n = len(s)
    periods = periods or [str(i) for i in range(n)]
    empty = {
        "slope": 0.0,
        "intercept": float(s.iloc[0]) if n else 0.0,
        "direction": "flat",
        "mann_kendall_tau": 0.0,
        "mann_kendall_p": 1.0,
        "significant": False,
        "n": n,
        "first_period": periods[0] if periods else None,
        "last_period": periods[-1] if periods else None,
    }
    if n < 3:
        return empty

    x = np.arange(n, dtype=float)
    y = s.to_numpy(dtype=float)
    slope, intercept, *_ = stats.theilslopes(y, x)
    # Mann-Kendall via Kendall tau (equivalent for trend test)
    tau, p_value = stats.kendalltau(x, y)
    if np.isnan(tau):
        tau, p_value = 0.0, 1.0
    significant = bool(p_value < alpha)
    if abs(slope) < 1e-12 or not significant:
        direction = "flat"
    elif slope > 0:
        direction = "up"
    else:
        direction = "down"
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "direction": direction,
        "mann_kendall_tau": float(tau),
        "mann_kendall_p": float(p_value),
        "significant": significant,
        "n": n,
        "first_period": periods[0],
        "last_period": periods[-1],
    }


def has_stl() -> bool:
    """Whether statsmodels STL is available in this environment."""
    return _HAS_STL
