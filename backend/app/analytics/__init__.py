"""Pure analytics math — zero I/O, zero LLM (Phase H).

All functions here must stay offline-testable (INV-2). Services that talk to
SQL / SQLite / Ollama live under ``backend.app.services``.
"""

from backend.app.analytics.contribution import (
    concentration_hhi,
    contribution_breakdown,
    detect_churn_customers,
    detect_new_customers,
    pareto_champions,
)
from backend.app.analytics.detectors import (
    detect_anomalies,
    detect_changepoints,
    detect_trend,
)
from backend.app.analytics.forecasting import forecast_baseline, forecast_residual_flags

__all__ = [
    "concentration_hhi",
    "contribution_breakdown",
    "detect_anomalies",
    "detect_changepoints",
    "detect_churn_customers",
    "detect_new_customers",
    "detect_trend",
    "forecast_baseline",
    "forecast_residual_flags",
    "pareto_champions",
]
