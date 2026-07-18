"""Insight ranker (Phase J) — heuristic by default; logistic regression once
enough real feedback exists.

Locked gate constants (roadmap §4.2, INV-8 — names/values are frozen, do not
rename or change without owner approval + roadmap update in the same commit):
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger
from backend.app.services import insight_store
from backend.app.services.local_paths import get_local_dir

MIN_LABELS_FOR_ML = 100
MIN_AUC_GATE = 0.6

_DETECTORS = ("anomaly", "changepoint", "trend", "forecast_residual")
_write_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    d = get_local_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d / "insight_ranker.pkl"


def _events_path() -> Path:
    d = get_local_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "ranker_events.jsonl"


def _log_event(event: dict[str, Any]) -> None:
    """Every heuristic<->ML switch and retrain must be logged (INV-8 [REVIEW])
    — same append-only-JSONL idiom as pdca_logger.py, no new mechanism."""
    record = {"at": _utc_now(), **event}
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with _write_lock:
        with _events_path().open("a", encoding="utf-8") as f:
            f.write(line)
    logger.info("insight_ranker event: %s", record)


def _recency_days(timestamp: str | None) -> float:
    if not timestamp:
        return 0.0
    try:
        ts = datetime.fromisoformat(timestamp)
    except ValueError:
        return 0.0
    return max((datetime.now(timezone.utc) - ts).total_seconds() / 86400.0, 0.0)


def _features_from_dict(d: dict[str, Any]) -> list[float]:
    """Feature vector shared by training (insight_store rows) and scoring
    (fresh insight_pipeline candidates) — both shapes carry these keys."""
    significance = float(d.get("significance") if d.get("significance") is not None else d.get("raw_significance") or 0.0)
    impact = float(d.get("impact") or 0.0)
    novelty = float(d.get("novelty") if d.get("novelty") is not None else 1.0)
    recency = _recency_days(d.get("created_at") or d.get("published_at"))
    detector = d.get("detector") or ""
    one_hot = [1.0 if detector == name else 0.0 for name in _DETECTORS]
    return [significance, impact, novelty, recency, *one_hot]


FEATURE_NAMES = ["significance", "impact", "novelty", "recency_days", *(f"is_{d}" for d in _DETECTORS)]


def heuristic_score(insight: dict[str, Any]) -> float:
    """The same significance x impact x novelty formula insight_pipeline
    already computes — kept here too so training/scoring can fall back to
    an identical baseline without importing insight_pipeline (avoids a
    circular import; insight_pipeline imports this module, not vice versa)."""
    significance = float(insight.get("significance") if insight.get("significance") is not None else insight.get("raw_significance") or 0.0)
    impact = float(insight.get("impact") or 0.0)
    novelty = float(insight.get("novelty") if insight.get("novelty") is not None else 1.0)
    return round(significance * impact * novelty, 6)


def _labeled_dataset(*, db_path: Any = None) -> tuple[list[list[float]], list[int]]:
    feedback_rows = insight_store.list_feedback(db_path=db_path)
    X: list[list[float]] = []
    y: list[int] = []
    for fb in feedback_rows:
        insight = insight_store.get_insight(fb["insight_id"], db_path=db_path)
        if insight is None:
            continue
        X.append(_features_from_dict(insight))
        y.append(1 if fb["label"] == "useful" else 0)
    return X, y


def train_ranker(
    *,
    min_labels: int = MIN_LABELS_FOR_ML,
    min_auc: float = MIN_AUC_GATE,
    db_path: Any = None,
    model_path: Path | None = None,
) -> dict[str, Any]:
    """Train + AUC-gate a logistic-regression ranker. Heuristic stays active
    (and this function is a safe no-op on the scoring path) until there are
    >= min_labels real feedback rows AND holdout AUC >= min_auc."""
    X, y = _labeled_dataset(db_path=db_path)
    n_labels = len(y)
    if n_labels < min_labels:
        result = {"status": "insufficient_labels", "n_labels": n_labels, "min_labels": min_labels}
        _log_event(result)
        return result
    if len(set(y)) < 2:
        result = {"status": "single_class_labels", "n_labels": n_labels}
        _log_event(result)
        return result

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_holdout_scaled = scaler.transform(X_holdout)

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train_scaled, y_train)
    proba = model.predict_proba(X_holdout_scaled)[:, 1]
    auc = float(roc_auc_score(y_holdout, proba))

    passed = auc >= min_auc
    if passed:
        import joblib

        payload = {
            "model": model,
            "scaler": scaler,
            "feature_names": FEATURE_NAMES,
            "auc": auc,
            "n_labels": n_labels,
            "trained_at": _utc_now(),
            "passed_gate": True,
        }
        joblib.dump(payload, _model_path(model_path))

    result = {
        "status": "promoted" if passed else "kept_heuristic",
        "n_labels": n_labels,
        "auc": auc,
        "min_auc": min_auc,
    }
    _log_event(result)
    return result


def is_ml_active(*, model_path: Path | None = None) -> bool:
    path = _model_path(model_path)
    if not path.exists():
        return False
    try:
        import joblib

        payload = joblib.load(path)
        return bool(payload.get("passed_gate")) and payload.get("model") is not None
    except Exception:
        logger.warning("insight_ranker: could not load model at %s", path, exc_info=True)
        return False


def _predict(insights: list[dict[str, Any]], *, model_path: Path | None = None) -> list[float] | None:
    try:
        import joblib

        payload = joblib.load(_model_path(model_path))
        X = [_features_from_dict(i) for i in insights]
        X_scaled = payload["scaler"].transform(X)
        return [float(p) for p in payload["model"].predict_proba(X_scaled)[:, 1]]
    except Exception:
        logger.warning("insight_ranker: prediction failed, falling back to heuristic", exc_info=True)
        return None


def apply_ranker(
    candidates: list[dict[str, Any]], *, model_path: Path | None = None
) -> list[dict[str, Any]]:
    """Called from insight_pipeline's score_candidates step. A pure no-op
    (returns candidates unchanged) while ML is dormant — behavior-preserving
    by construction, verified by tests."""
    if not candidates or not is_ml_active(model_path=model_path):
        return candidates
    scores = _predict(candidates, model_path=model_path)
    if scores is None:
        return candidates
    for c, score in zip(candidates, scores):
        c["rank_score"] = round(score, 6)
    return candidates


def score_insights(
    insights: list[dict[str, Any]], *, model_path: Path | None = None
) -> list[dict[str, Any]]:
    """Standalone scoring entry point (e.g. for a future re-rank of the feed)."""
    if is_ml_active(model_path=model_path):
        scores = _predict(insights, model_path=model_path)
        if scores is not None:
            for i, score in zip(insights, scores):
                i["rank_score"] = round(score, 6)
            return sorted(insights, key=lambda i: i["rank_score"], reverse=True)
    for i in insights:
        i.setdefault("rank_score", heuristic_score(i))
    return sorted(insights, key=lambda i: i["rank_score"], reverse=True)
