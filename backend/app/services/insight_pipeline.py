"""Proactive insight pipeline (Phase I).

Five steps, each reusable in isolation and reported to job progress:
``refresh_snapshots -> run_detectors -> score_candidates -> narrate_top -> publish``.

Evidence-first (roadmap §2 item 1): every number quoted in a narrative must
already exist in that insight's evidence JSON. ``validate_narrative_numbers``
enforces this (INV-4) — a narrative that fails gets one retry, then falls
back to a deterministic template that can never hallucinate a number.
"""

from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from backend.app.analytics.detectors import detect_anomalies, detect_changepoints, detect_trend
from backend.app.analytics.forecasting import forecast_residual_flags
from backend.app.core.config import get_settings
from backend.app.core.llm import make_chat_ollama
from backend.app.core.logger import logger
from backend.app.services import insight_store, snapshot_store
from backend.app.services.metric_registry import list_metrics
from backend.app.services.snapshot_refresh_service import refresh_snapshots

# Only look at the most recent N months of each series each run — anomalies
# from deep history were already surfaced (or suppressed) by a prior run.
_RECENT_WINDOW = 2
_NOVELTY_WINDOW_DAYS = 60
_MIN_SERIES_LEN = 4

_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?%?")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Evidence-first numeric validator (INV-4)
# ---------------------------------------------------------------------------


def _flatten_numbers(obj: Any) -> list[float]:
    """Collect every numeric leaf in ``obj``, each also contributing its
    absolute value — a narrative saying "decreased by 500" for a stored
    ``delta: -500.0`` is a faithful restatement (direction is already carried
    by the Thai verb), not a hallucination, so sign alone must not fail it."""
    nums: list[float] = []
    if isinstance(obj, bool):
        return nums
    if isinstance(obj, (int, float)):
        nums.append(float(obj))
        nums.append(abs(float(obj)))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums.extend(_flatten_numbers(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nums.extend(_flatten_numbers(v))
    elif isinstance(obj, str):
        for m in _NUMBER_RE.findall(obj):
            cleaned = m.replace(",", "").rstrip("%")
            try:
                nums.append(float(cleaned))
            except ValueError:
                continue
    return nums


def _extract_narrative_numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUMBER_RE.findall(text):
        cleaned = m.replace(",", "").rstrip("%")
        try:
            out.append(float(cleaned))
        except ValueError:
            continue
    return out


def validate_narrative_numbers(
    narrative_th: str,
    evidence: dict[str, Any],
    *,
    rel_tol: float = 0.01,
    abs_tol: float = 0.5,
) -> bool:
    """Every number quoted in ``narrative_th`` must appear (within tolerance)
    somewhere in ``evidence`` — the LLM narrates, it never invents numbers.

    Small non-negative integers (<=12) are exempt: ordinary Thai prose uses
    them for counts/ordinals ("3 เดือน", "อันดับ 1") that are not numeric
    *claims* about the business, and would otherwise fail validation on
    entirely incidental phrasing.
    """
    known = _flatten_numbers(evidence)
    quoted = _extract_narrative_numbers(narrative_th)
    for q in quoted:
        if 0 <= q <= 12 and float(q).is_integer():
            continue
        if not any(abs(q - k) <= max(abs_tol, rel_tol * abs(k)) for k in known):
            return False
    return True


# ---------------------------------------------------------------------------
# Step 1: refresh_snapshots — delegates to Phase H (INV-3 already enforced there)
# ---------------------------------------------------------------------------


async def _step_refresh_snapshots(db_path: Any) -> dict[str, Any]:
    try:
        return await refresh_snapshots(mode="auto", db_path=db_path)
    except Exception as exc:
        logger.warning("Insight pipeline: snapshot refresh skipped (%s)", exc)
        return {"status": "skipped", "error": str(exc)}


# ---------------------------------------------------------------------------
# Step 2: run_detectors — build raw candidates from the pure Phase H detectors
# ---------------------------------------------------------------------------


def _series_source(series: list[dict[str, Any]], period: str) -> str | None:
    for row in series:
        if row["period"] == period:
            return row.get("source")
    return None


def _build_candidate(
    *,
    metric_key: str,
    detector: str,
    period: str,
    direction: str,
    value: float,
    baseline: float,
    raw_significance: float,
    theme_id: str | None,
    series_source: str | None,
    extra_evidence: dict[str, Any],
) -> dict[str, Any]:
    delta = value - baseline
    impact = min(abs(delta) / (abs(baseline) + 1e-9), 1.0) if baseline else 1.0
    return {
        "metric_key": metric_key,
        "detector": detector,
        "dim_name": "__total__",
        "dim_value": "__total__",
        "period": period,
        "direction": direction,
        "magnitude": abs(delta),
        "raw_significance": raw_significance,
        "impact": impact,
        "theme_id": theme_id,
        "source": series_source,
        "evidence": {
            "metric_key": metric_key,
            "detector": detector,
            "period": period,
            "direction": direction,
            "value": value,
            "baseline": baseline,
            "delta": delta,
            "source": series_source,
            **extra_evidence,
        },
    }


def _candidates_for_metric(
    metric_key: str, *, theme_id: str | None, db_path: Any
) -> list[dict[str, Any]]:
    series = snapshot_store.get_series(metric_key, db_path=db_path)
    if len(series) < _MIN_SERIES_LEN:
        return []
    periods = [r["period"] for r in series]
    values = [float(r["value"] or 0.0) for r in series]
    baseline = statistics.median(values)
    recent_periods = set(periods[-_RECENT_WINDOW:])
    out: list[dict[str, Any]] = []

    for event in detect_anomalies(values, periods=periods):
        if event["period"] not in recent_periods:
            continue
        out.append(
            _build_candidate(
                metric_key=metric_key,
                detector="anomaly",
                period=event["period"],
                direction=event["direction"],
                value=event["value"],
                baseline=baseline,
                raw_significance=min(event["significance"] / 6.0, 1.0),
                theme_id=theme_id,
                series_source=_series_source(series, event["period"]),
                extra_evidence={"methods": event["methods"], "scores": event["scores"]},
            )
        )

    for event in detect_changepoints(values, periods=periods):
        if event["period"] not in recent_periods:
            continue
        out.append(
            _build_candidate(
                metric_key=metric_key,
                detector="changepoint",
                period=event["period"],
                direction=event["direction"],
                value=event["value"],
                baseline=baseline,
                raw_significance=min(event["significance"], 1.0),
                theme_id=theme_id,
                series_source=_series_source(series, event["period"]),
                extra_evidence={"cusum": event["cusum"], "threshold": event["threshold"]},
            )
        )

    trend = detect_trend(values, periods=periods)
    if trend["significant"] and trend["direction"] != "flat" and trend["last_period"] in recent_periods:
        out.append(
            _build_candidate(
                metric_key=metric_key,
                detector="trend",
                period=trend["last_period"],
                direction=trend["direction"],
                value=values[-1],
                baseline=baseline,
                raw_significance=min(1.0 - trend["mann_kendall_p"], 1.0),
                theme_id=theme_id,
                series_source=_series_source(series, trend["last_period"]),
                extra_evidence={
                    "slope": trend["slope"],
                    "mann_kendall_p": trend["mann_kendall_p"],
                    "n_periods": trend["n"],
                },
            )
        )

    for event in forecast_residual_flags(values, periods=periods):
        if event["period"] not in recent_periods:
            continue
        out.append(
            _build_candidate(
                metric_key=metric_key,
                detector="forecast_residual",
                period=event["period"],
                direction=event["direction"],
                value=event["value"],
                baseline=baseline,
                raw_significance=min(event["significance"] / 4.0, 1.0),
                theme_id=theme_id,
                series_source=_series_source(series, event["period"]),
                extra_evidence={"forecast": event["forecast"], "residual": event["residual"]},
            )
        )
    return out


async def _step_run_detectors(*, theme_id: str | None, db_path: Any) -> list[dict[str, Any]]:
    entries = await list_metrics(approved_only=True)
    base_keys = [e["metric_key"] for e in entries if not e.get("derived") and e.get("expression")]
    candidates: list[dict[str, Any]] = []
    for key in base_keys:
        candidates.extend(_candidates_for_metric(key, theme_id=theme_id, db_path=db_path))
    return candidates


# ---------------------------------------------------------------------------
# Step 3: score_candidates — significance x impact x novelty (roadmap §8)
# ---------------------------------------------------------------------------


def _novelty_score(
    key: tuple[str, str, str, str],
    recent_map: dict[tuple[str, str, str, str], str],
    *,
    now: datetime,
    window_days: int = _NOVELTY_WINDOW_DAYS,
) -> float:
    last_iso = recent_map.get(key)
    if not last_iso:
        return 1.0
    try:
        last = datetime.fromisoformat(last_iso)
    except ValueError:
        return 1.0
    age_days = (now - last).total_seconds() / 86400.0
    if age_days <= 0:
        return 0.0
    if age_days >= window_days:
        return 1.0
    return round(age_days / window_days, 4)


def _score_candidates(candidates: list[dict[str, Any]], *, db_path: Any) -> list[dict[str, Any]]:
    recent_map = insight_store.recent_published_map(window_days=_NOVELTY_WINDOW_DAYS, db_path=db_path)
    now = datetime.now(timezone.utc)
    for c in candidates:
        key = (c["metric_key"], c["dim_name"], c["dim_value"], c["direction"])
        novelty = _novelty_score(key, recent_map, now=now)
        score = round(c["raw_significance"] * c["impact"] * novelty, 6)
        c["novelty"] = novelty
        c["significance"] = c["raw_significance"]
        c["score"] = score
        c["rank_score"] = score  # heuristic today; Phase J ranker may overwrite
        # Near-zero novelty means an identical insight published very recently
        # — quiet it immediately (lifecycle: suppressed via novelty dedupe).
        c["status"] = "suppressed" if novelty < 0.05 else "scored"

    # Phase J: overrides rank_score with the trained model's prediction once
    # >=100 real labels exist and it clears the AUC gate; a pure no-op today
    # (0 labels) — heuristic rank_score above is untouched.
    from backend.app.services.insight_ranker import apply_ranker

    candidates = apply_ranker(candidates)
    candidates.sort(key=lambda c: c["rank_score"], reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Step 4: narrate_top — evidence-only Ollama narration + validator + fallback
# ---------------------------------------------------------------------------

_NARRATE_PROMPT = """คุณคือนักวิเคราะห์ข้อมูลที่เล่าเรื่องจาก evidence เท่านั้น ห้ามคิดตัวเลขเอง
ใช้เฉพาะตัวเลขที่ปรากฏใน evidence JSON ด้านล่าง ห้ามประมาณค่าหรือแต่งตัวเลขใหม่

Evidence:
{evidence_json}

เขียนคำอธิบายภาษาไทย 3-5 ประโยค อธิบายว่าเกิดอะไรขึ้น (metric, ช่วงเวลา, ทิศทาง, ขนาดการเปลี่ยนแปลง)
แล้วจบด้วยคำถามต่อยอด 1 ข้อที่ชวนให้ตรวจสอบสาเหตุต่อ ห้ามใส่ตัวเลขที่ไม่อยู่ใน evidence ข้างต้น"""

_RENARRATE_SUFFIX = """

(รอบก่อนหน้าใส่ตัวเลขที่ไม่อยู่ใน evidence — รอบนี้ใช้เฉพาะตัวเลขที่เห็นใน evidence ด้านบนเท่านั้น)"""

_DIRECTION_TH = {"up": "เพิ่มขึ้น", "down": "ลดลง", "flat": "ทรงตัว"}


async def _call_narrator(evidence: dict[str, Any], *, retry: bool = False) -> str | None:
    prompt = _NARRATE_PROMPT.format(evidence_json=json.dumps(evidence, ensure_ascii=False, default=str))
    if retry:
        prompt += _RENARRATE_SUFFIX
    try:
        llm = make_chat_ollama(temperature=0.2)
        response = await llm.ainvoke(prompt)
        text = str(response.content).strip()
        return text or None
    except Exception as exc:
        logger.warning("Insight narration failed: %s", exc)
        return None


def _fallback_narrative(candidate: dict[str, Any]) -> str:
    direction_th = _DIRECTION_TH.get(candidate["direction"], candidate["direction"])
    return (
        f"ระบบตรวจพบว่า {candidate['metric_key']} ในช่วง {candidate['period']} "
        f"{direction_th} อย่างมีนัยสำคัญ (ขนาดการเปลี่ยนแปลงโดยประมาณ {candidate['magnitude']:,.2f}, "
        f"ตรวจจับด้วยวิธี {candidate['detector']}) ควรตรวจสอบสาเหตุเพิ่มเติมกับทีมธุรกิจที่เกี่ยวข้อง "
        "ว่ามีเหตุการณ์ใดในช่วงเวลานี้หรือไม่?"
    )


async def _narrate_with_validation(candidate: dict[str, Any]) -> str:
    text = await _call_narrator(candidate["evidence"])
    if text and validate_narrative_numbers(text, candidate["evidence"]):
        return text
    if text:
        logger.warning(
            "Insight narrative failed numeric validation for %s/%s — retrying",
            candidate["metric_key"],
            candidate["period"],
        )
    retried = await _call_narrator(candidate["evidence"], retry=True)
    if retried and validate_narrative_numbers(retried, candidate["evidence"]):
        return retried
    return _fallback_narrative(candidate)


async def _step_narrate_top(candidates: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    eligible = [c for c in candidates if c["status"] == "scored"]
    top = eligible[:top_k]
    for c in top:
        c["narrative_th"] = await _narrate_with_validation(c)
        c["narrated_at"] = _utc_now()
        c["status"] = "narrated"
    return candidates


# ---------------------------------------------------------------------------
# Step 5: publish — persist every candidate (top-K narrated+published; the
# rest stay as scored/suppressed rows for future lazy-narrate/audit)
# ---------------------------------------------------------------------------


def _step_publish(candidates: list[dict[str, Any]], *, run_id: str, db_path: Any) -> dict[str, int]:
    published = 0
    suppressed = 0
    scored = 0
    for c in candidates:
        status = c["status"]
        published_at = _utc_now() if status == "narrated" else None
        insight_store.create_insight(
            theme_id=c.get("theme_id"),
            metric_key=c["metric_key"],
            detector=c["detector"],
            dim_name=c["dim_name"],
            dim_value=c["dim_value"],
            period=c["period"],
            direction=c["direction"],
            magnitude=c["magnitude"],
            significance=c["significance"],
            impact=c["impact"],
            novelty=c["novelty"],
            score=c["score"],
            rank_score=c["rank_score"],
            status="published" if status == "narrated" else status,
            evidence=c["evidence"],
            run_id=run_id,
            source=c.get("source"),
            narrative_th=c.get("narrative_th"),
            narrated_at=c.get("narrated_at"),
            published_at=published_at,
            db_path=db_path,
        )
        if status == "narrated":
            published += 1
        elif status == "suppressed":
            suppressed += 1
        else:
            scored += 1
    return {"published": published, "suppressed": suppressed, "scored": scored}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run_insight_pipeline(
    *,
    theme_id: str | None = None,
    top_k: int | None = None,
    step_cb: Callable[[str], None] | None = None,
    db_path: Any = None,
) -> dict[str, Any]:
    """Run the full proactive pipeline once and return a summary dict."""
    settings = get_settings()
    top_k = top_k if top_k is not None else settings.insight_narrate_top_k
    run_id = uuid4().hex
    insight_store.init_insight_tables(db_path)

    if step_cb:
        step_cb("refresh_snapshots")
    refresh_result = await _step_refresh_snapshots(db_path)

    if step_cb:
        step_cb("run_detectors")
    candidates = await _step_run_detectors(theme_id=theme_id, db_path=db_path)

    if step_cb:
        step_cb("score_candidates")
    candidates = _score_candidates(candidates, db_path=db_path)

    if step_cb:
        step_cb("narrate_top")
    candidates = await _step_narrate_top(candidates, top_k=top_k)

    if step_cb:
        step_cb("publish")
    counts = _step_publish(candidates, run_id=run_id, db_path=db_path)

    digest_result = None
    if settings.digest_enabled and settings.digest_after_pipeline:
        if step_cb:
            step_cb("board_digest")
        try:
            from backend.app.services import digest_service

            digest_result = await digest_service.generate_digest(polish=None, db_path=db_path)
        except Exception as exc:
            logger.warning("Board digest after pipeline skipped: %s", type(exc).__name__)
            digest_result = {"status": "skipped", "error": type(exc).__name__}

    return {
        "run_id": run_id,
        "refresh": refresh_result,
        "candidates_total": len(candidates),
        **counts,
        "digest": digest_result,
    }
