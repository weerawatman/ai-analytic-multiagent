"""Background scheduler for the proactive insight pipeline (Phase I).

Catch-up-on-startup is the primary trigger (roadmap §3): if the latest
``insight_pipeline`` job is older than ``insight_catchup_after_hours`` (or
none has ever run), one gets enqueued shortly after backend start. A nightly
cron at ``insight_cron_hour`` is a bonus, not the primary mechanism. Both
paths always defer when a chat/onboarding job is active — this project runs
a single local Ollama instance, so background narration must never compete
with a live user question (INV-6: enqueue only through ``job_runner``, never
threading/multiprocessing/subprocess).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import backend.app.services.job_runner as job_runner

from backend.app.core.config import get_settings
from backend.app.core.logger import logger
from backend.app.services import job_store

_CATCHUP_DELAY_SECONDS = 120
_BUSY_KINDS = ("chat", "onboarding", "deep_onboarding")
_PIPELINE_THREAD_ID = "analytics:insight_pipeline"

_scheduler: AsyncIOScheduler | None = None


def _ollama_busy() -> bool:
    """True when a chat/onboarding/deep_onboarding job is currently active."""
    return any(job_store.list_jobs(kind=kind, active_only=True, limit=1) for kind in _BUSY_KINDS)


def _last_pipeline_job() -> dict | None:
    jobs = job_store.list_jobs(kind="insight_pipeline", limit=1)
    return jobs[0] if jobs else None


def _enqueue(reason: str) -> None:
    settings = get_settings()
    if not settings.insight_pipeline_enabled:
        return
    if _ollama_busy():
        logger.info("Insight pipeline (%s) deferred — chat/onboarding job active", reason)
        return
    existing = job_store.find_active_job("insight_pipeline", _PIPELINE_THREAD_ID)
    if existing is not None:
        return
    logger.info("Enqueuing insight_pipeline job (%s)", reason)
    job_runner.start_insight_pipeline_job()


def _catchup_check() -> None:
    settings = get_settings()
    if not settings.insight_pipeline_enabled:
        return
    last = _last_pipeline_job()
    if last is None or last.get("status") != "done":
        _enqueue("catch-up: never completed")
        return
    finished_at = last.get("finished_at")
    try:
        age_hours = (
            datetime.now(timezone.utc) - datetime.fromisoformat(finished_at)
        ).total_seconds() / 3600.0
    except (TypeError, ValueError):
        age_hours = settings.insight_catchup_after_hours + 1
    if age_hours >= settings.insight_catchup_after_hours:
        _enqueue(f"catch-up: last run {age_hours:.1f}h ago")


def _nightly_job() -> None:
    _enqueue("nightly cron")


def start(scheduler: AsyncIOScheduler | None = None) -> AsyncIOScheduler:
    """Start the scheduler (idempotent) — called from the FastAPI lifespan."""
    global _scheduler
    settings = get_settings()
    sched = scheduler or AsyncIOScheduler()
    run_date = datetime.now(timezone.utc) + timedelta(seconds=_CATCHUP_DELAY_SECONDS)
    sched.add_job(_catchup_check, "date", run_date=run_date, id="insight_catchup", replace_existing=True)
    sched.add_job(
        _nightly_job,
        CronTrigger(hour=settings.insight_cron_hour, minute=0),
        id="insight_nightly",
        replace_existing=True,
    )
    if not sched.running:
        sched.start()
    _scheduler = sched
    return sched


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
