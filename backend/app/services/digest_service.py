"""Board digest — weekly/monthly board pack (Phase K).

Reuses insight + snapshot stores (read-only). Writes JSON under
``data/local/briefings/digests/{yyyy-ww}.json``. Optional Claude polish
goes through consultant redaction/audit; failures never block the base digest.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services import insight_store, snapshot_store
from backend.app.services.local_paths import get_local_dir

# O-3 still open: reuse calendar YYYYMM from snapshot store and label clearly.
PERIOD_BASIS = "calendar_yyyymm_provisional"


def digests_dir() -> Path:
    path = get_local_dir() / "briefings" / "digests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def iso_week_key(when: datetime | None = None) -> str:
    """ISO week key ``yyyy-ww`` (week 01–53)."""
    dt = when or datetime.now(timezone.utc)
    iso = dt.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def digest_path(week_key: str | None = None) -> Path:
    return digests_dir() / f"{week_key or iso_week_key()}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shift_yyyymm(period: str, months: int) -> str | None:
    if not period or len(period) != 6 or not period.isdigit():
        return None
    year, month = int(period[:4]), int(period[4:6])
    idx = year * 12 + (month - 1) + months
    return f"{idx // 12}{(idx % 12) + 1:02d}"


def _sum_periods(series: list[dict[str, Any]], periods: list[str]) -> float | None:
    by_p = {r["period"]: r.get("value") for r in series}
    vals: list[float] = []
    for p in periods:
        v = by_p.get(p)
        if v is None:
            return None
        vals.append(float(v))
    return sum(vals)


def _pct_delta(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    if prior == 0:
        return None if current == 0 else 100.0
    return round(100.0 * (current - prior) / abs(prior), 2)


def list_published_useful_insights(
    *,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Published insights whose **latest** feedback label is ``useful``."""
    insight_store.init_insight_tables(db_path)
    with snapshot_store.get_analytics_connection(db_path) as conn:
        rows = conn.execute(
            """
            WITH latest_fb AS (
                SELECT insight_id, label,
                       ROW_NUMBER() OVER (
                           PARTITION BY insight_id ORDER BY created_at DESC
                       ) AS rn
                FROM insight_feedback
            )
            SELECT i.*
            FROM insights i
            INNER JOIN latest_fb f ON f.insight_id = i.id AND f.rn = 1
            WHERE i.status = 'published' AND f.label = 'useful'
            ORDER BY coalesce(i.published_at, i.created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [insight_store._row_to_insight(r) for r in rows]


def compute_qoq_yoy(
    metric_key: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Calendar-quarter QoQ/YoY from monthly ``__total__`` snapshots."""
    series = snapshot_store.get_series(
        metric_key, dim_name="__total__", dim_value="__total__", db_path=db_path
    )
    empty = {
        "metric_key": metric_key,
        "period_basis": PERIOD_BASIS,
        "anchor_period": None,
        "current_quarter": None,
        "prior_quarter": None,
        "yoy_quarter": None,
        "qoq_pct": None,
        "yoy_pct": None,
        "source": None,
    }
    if not series:
        return empty

    anchor = series[-1]["period"]
    cq = [anchor]
    for i in range(1, 3):
        p = _shift_yyyymm(anchor, -i)
        if p:
            cq.append(p)
    cq = list(reversed(cq))

    pq = []
    for p in cq:
        prior = _shift_yyyymm(p, -3)
        if prior:
            pq.append(prior)

    yq = []
    for p in cq:
        yoy = _shift_yyyymm(p, -12)
        if yoy:
            yq.append(yoy)

    current = _sum_periods(series, cq)
    prior = _sum_periods(series, pq) if len(pq) == 3 else None
    yoy = _sum_periods(series, yq) if len(yq) == 3 else None
    source = series[-1].get("source")

    return {
        "metric_key": metric_key,
        "period_basis": PERIOD_BASIS,
        "anchor_period": anchor,
        "current_quarter_periods": cq,
        "current_quarter": current,
        "prior_quarter": prior,
        "yoy_quarter": yoy,
        "qoq_pct": _pct_delta(current, prior),
        "yoy_pct": _pct_delta(current, yoy),
        "source": source,
    }


def metric_summary_rows(
    *,
    metric_keys: list[str] | None = None,
    limit: int = 12,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Latest value + QoQ/YoY for approved/snapshot metrics."""
    if metric_keys is None:
        with snapshot_store.get_analytics_connection(db_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT metric_key FROM metric_snapshots
                ORDER BY metric_key LIMIT ?
                """,
                (limit,),
            ).fetchall()
        metric_keys = [r["metric_key"] for r in rows]

    out: list[dict[str, Any]] = []
    for key in metric_keys[:limit]:
        series = snapshot_store.get_series(
            key, dim_name="__total__", dim_value="__total__", db_path=db_path
        )
        latest = series[-1] if series else None
        qoy = compute_qoq_yoy(key, db_path=db_path)
        out.append(
            {
                "metric_key": key,
                "latest_period": latest["period"] if latest else None,
                "latest_value": latest.get("value") if latest else None,
                "source": latest.get("source") if latest else None,
                "refreshed_at": latest.get("refreshed_at") if latest else None,
                "qoq_pct": qoy.get("qoq_pct"),
                "yoy_pct": qoy.get("yoy_pct"),
                "period_basis": PERIOD_BASIS,
            }
        )
    return out


async def _optional_polish(digest: dict[str, Any]) -> str | None:
    """Claude polish — soft-fail; requires consultant + polish flag."""
    settings = get_settings()
    if not settings.consultant_is_enabled or not settings.consultant_polish_digest:
        return None
    try:
        from backend.app.services import consultant_service
        from backend.app.services.consultant_redaction import redact_for_external

        payload = {
            "week_key": digest.get("week_key"),
            "insight_count": len(digest.get("insights") or []),
            "metric_summaries": digest.get("metric_summaries") or [],
            "insights": [
                {
                    "metric_key": i.get("metric_key"),
                    "period": i.get("period"),
                    "narrative_th": (i.get("narrative_th") or "")[:800],
                    "source": i.get("source"),
                }
                for i in (digest.get("insights") or [])[:10]
            ],
        }
        text = redact_for_external(json.dumps(payload, ensure_ascii=False))
        note = await consultant_service.answer_question(
            "",
            (
                "ขัดเกลาสรุปผู้บริหารภาษาไทยสั้นๆ จาก board digest JSON ด้านล่าง "
                "ห้าม invent ตัวเลขใหม่ — ใช้เฉพาะตัวเลขในข้อมูล\n\n" + text[:6000]
            ),
        )
        return (note or "").strip() or None
    except Exception as exc:
        logger.warning("Digest polish skipped: %s", type(exc).__name__)
        return None


async def generate_digest(
    *,
    week_key: str | None = None,
    polish: bool | None = None,
    insight_limit: int = 20,
    metric_limit: int = 12,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build and persist a weekly board digest."""
    key = week_key or iso_week_key()
    insights = list_published_useful_insights(limit=insight_limit, db_path=db_path)
    summaries = metric_summary_rows(limit=metric_limit, db_path=db_path)
    qoy_tables = [
        compute_qoq_yoy(s["metric_key"], db_path=db_path)
        for s in summaries
        if s.get("metric_key")
    ]

    digest: dict[str, Any] = {
        "week_key": key,
        "generated_at": _utc_now(),
        "period_basis": PERIOD_BASIS,
        "insights": [
            {
                "id": i.get("id"),
                "theme_id": i.get("theme_id"),
                "metric_key": i.get("metric_key"),
                "detector": i.get("detector"),
                "period": i.get("period"),
                "direction": i.get("direction"),
                "narrative_th": i.get("narrative_th"),
                "source": i.get("source"),
                "score": i.get("score"),
            }
            for i in insights
        ],
        "metric_summaries": summaries,
        "qoq_yoy": qoy_tables,
        "polish_th": None,
        "counts": {
            "useful_insights": len(insights),
            "metrics": len(summaries),
        },
    }

    settings = get_settings()
    do_polish = settings.consultant_polish_digest if polish is None else polish
    if do_polish:
        digest["polish_th"] = await _optional_polish(digest)

    path = digest_path(key)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(digest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    digest["path"] = str(path)
    return digest


def load_digest(week_key: str | None = None) -> dict[str, Any] | None:
    path = digest_path(week_key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_digests(*, limit: int = 12) -> list[dict[str, Any]]:
    """Newest digests first (summary only)."""
    files = sorted(digests_dir().glob("*.json"), reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "week_key": doc.get("week_key") or path.stem,
                "generated_at": doc.get("generated_at"),
                "counts": doc.get("counts") or {},
                "period_basis": doc.get("period_basis"),
                "has_polish": bool(doc.get("polish_th")),
            }
        )
    return out
