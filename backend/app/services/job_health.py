"""Job status enrichment helpers (heartbeat age + health)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Roadmap G1: stalled = heartbeat age ≥ 30s while job is still active.
STALLED_AFTER_SECONDS = 30.0


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def enrich_job_status(job: dict[str, Any]) -> dict[str, Any]:
    """Add heartbeat_age_s and health for API responses."""
    out = dict(job)
    hb = _parse_iso(job.get("heartbeat_at") or job.get("started_at"))
    status = job.get("status") or ""
    if status not in ("queued", "running"):
        out["heartbeat_age_s"] = None
        out["health"] = None
        return out
    if hb is None:
        out["heartbeat_age_s"] = None
        out["health"] = "stalled"
        return out
    age = (datetime.now(timezone.utc) - hb).total_seconds()
    out["heartbeat_age_s"] = round(age, 1)
    out["health"] = "stalled" if age >= STALLED_AFTER_SECONDS else "working"
    return out
