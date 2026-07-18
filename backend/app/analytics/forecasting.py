"""Baseline forecasting — seasonal naive always; ETS when statsmodels available."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # type: ignore

    _HAS_ETS = True
except Exception:  # pragma: no cover - optional dep
    ExponentialSmoothing = None  # type: ignore
    _HAS_ETS = False


def _to_series(values: list[float] | np.ndarray | pd.Series) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float).reset_index(drop=True)
    return pd.Series(np.asarray(values, dtype=float))


def seasonal_naive_forecast(
    values: list[float] | np.ndarray | pd.Series,
    *,
    horizon: int = 1,
    m: int = 12,
) -> dict[str, Any]:
    """Seasonal naive: ŷ_{t+h} = y_{t+h-m} (fallback to last value if short)."""
    s = _to_series(values)
    n = len(s)
    if n == 0:
        return {"method": "seasonal_naive", "point": [], "lower": [], "upper": [], "m": m}
    point: list[float] = []
    for h in range(1, horizon + 1):
        idx = n - m + (h - 1)
        if 0 <= idx < n:
            point.append(float(s.iloc[idx]))
        else:
            point.append(float(s.iloc[-1]))
    # Residual scale from in-sample seasonal-naive errors
    residuals: list[float] = []
    for i in range(m, n):
        residuals.append(float(s.iloc[i] - s.iloc[i - m]))
    if residuals:
        sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else abs(residuals[0])
    else:
        sigma = float(np.std(s.to_numpy(), ddof=1)) if n > 1 else 0.0
    sigma = max(sigma, 0.0)
    z = 1.96
    lower = [p - z * sigma for p in point]
    upper = [p + z * sigma for p in point]
    return {
        "method": "seasonal_naive",
        "point": point,
        "lower": lower,
        "upper": upper,
        "sigma": sigma,
        "m": m,
        "horizon": horizon,
    }


def ets_forecast(
    values: list[float] | np.ndarray | pd.Series,
    *,
    horizon: int = 1,
    m: int = 12,
) -> dict[str, Any] | None:
    """Holt-Winters ETS when statsmodels is available; else None."""
    if not _HAS_ETS or ExponentialSmoothing is None:
        return None
    s = _to_series(values)
    if len(s) < max(2 * m, 24):
        return None
    try:
        model = ExponentialSmoothing(
            s,
            seasonal_periods=m,
            trend="add",
            seasonal="add",
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True)
        fc = fit.forecast(horizon)
        resid = np.asarray(fit.resid, dtype=float)
        sigma = float(np.nanstd(resid, ddof=1)) if len(resid) > 1 else 0.0
        z = 1.96
        point = [float(v) for v in fc]
        return {
            "method": "ets",
            "point": point,
            "lower": [p - z * sigma for p in point],
            "upper": [p + z * sigma for p in point],
            "sigma": sigma,
            "m": m,
            "horizon": horizon,
        }
    except Exception:
        return None


def forecast_baseline(
    values: list[float] | np.ndarray | pd.Series,
    *,
    horizon: int = 1,
    m: int = 12,
    prefer_ets: bool = True,
) -> dict[str, Any]:
    """Prefer ETS when available; always fall back to seasonal naive."""
    if prefer_ets:
        ets = ets_forecast(values, horizon=horizon, m=m)
        if ets is not None:
            return ets
    return seasonal_naive_forecast(values, horizon=horizon, m=m)


def forecast_residual_flags(
    values: list[float] | np.ndarray | pd.Series,
    *,
    periods: list[str] | None = None,
    m: int = 12,
) -> list[dict[str, Any]]:
    """Flag periods where actual falls outside one-step seasonal-naive interval.

    For each t >= m, compare y_t to forecast from y_{t-m} ± 1.96σ.
    """
    s = _to_series(values)
    n = len(s)
    if n <= m:
        return []
    periods = periods or [str(i) for i in range(n)]
    residuals = [float(s.iloc[i] - s.iloc[i - m]) for i in range(m, n)]
    sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else abs(residuals[0])
    sigma = max(sigma, 0.0)
    z = 1.96
    events: list[dict[str, Any]] = []
    for i in range(m, n):
        pred = float(s.iloc[i - m])
        lo, hi = pred - z * sigma, pred + z * sigma
        actual = float(s.iloc[i])
        if actual < lo or actual > hi:
            events.append(
                {
                    "index": i,
                    "period": periods[i],
                    "value": actual,
                    "forecast": pred,
                    "lower": lo,
                    "upper": hi,
                    "direction": "up" if actual > hi else "down",
                    "residual": actual - pred,
                    "significance": abs(actual - pred) / (sigma + 1e-12),
                }
            )
    return events


def has_ets() -> bool:
    return _HAS_ETS
