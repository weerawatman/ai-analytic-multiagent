"""Background scheduler for insight pipeline + study jobs (Phase I/K).

Catch-up-on-startup is the primary trigger for insights (roadmap §3). Nightly
``study`` (Phase K) and optional Sunday digest generation enqueue only through
``job_runner`` / await digest_service from this process (INV-6: no
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
_BUSY_KINDS = ("chat", "onboarding", "deep_onboarding", "study")
_PIPELINE_THREAD_ID = "analytics:insight_pipeline"
_STUDY_THREAD_ID = "analytics:study"

_scheduler: AsyncIOScheduler | None = None


def _ollama_busy() -> bool:
    """True when a chat/onboarding/deep_onboarding/study job is currently active."""
    return any(job_store.list_jobs(kind=kind, active_only=True, limit=1) for kind in _BUSY_KINDS)


def _last_pipeline_job() -> dict | None:
    jobs = job_store.list_jobs(kind="insight_pipeline", limit=1)
    return jobs[0] if jobs else None


def _enqueue_insights(reason: str) -> None:
    settings = get_settings()
    if not settings.insight_pipeline_enabled:
        return
    if _ollama_busy():
        logger.info("Insight pipeline (%s) deferred — busy job active", reason)
        return
    existing = job_store.find_active_job("insight_pipeline", _PIPELINE_THREAD_ID)
    if existing is not None:
        return
    logger.info("Enqueuing insight_pipeline job (%s)", reason)
    job_runner.start_insight_pipeline_job()


def _enqueue_study(reason: str) -> None:
    settings = get_settings()
    if not settings.study_enabled:
        return
    if _ollama_busy():
        logger.info("Study job (%s) deferred — busy job active", reason)
        return
    existing = job_store.find_active_job("study", _STUDY_THREAD_ID)
    if existing is not None:
        return
    logger.info("Enqueuing study job (%s)", reason)
    job_runner.start_study_job(theme_id=settings.study_theme_id)


async def _weekly_digest() -> None:
    """Generate board digest in-process (no new job kind — §4.2 freeze)."""
    settings = get_settings()
    if not settings.digest_enabled:
        return
    if _ollama_busy() and settings.consultant_polish_digest:
        logger.info("Weekly digest deferred — busy (polish would need capacity)")
        return
    try:
        from backend.app.services import digest_service

        result = await digest_service.generate_digest()
        logger.info(
            "Weekly digest written week=%s insights=%s",
            result.get("week_key"),
            (result.get("counts") or {}).get("useful_insights"),
        )
    except Exception:
        logger.exception("Weekly digest failed")


def _catchup_check() -> None:
    settings = get_settings()
    if not settings.insight_pipeline_enabled:
        return
    last = _last_pipeline_job()
    if last is None or last.get("status") != "done":
        _enqueue_insights("catch-up: never completed")
        return
    finished_at = last.get("finished_at")
    try:
        age_hours = (
            datetime.now(timezone.utc) - datetime.fromisoformat(finished_at)
        ).total_seconds() / 3600.0
    except (TypeError, ValueError):
        age_hours = settings.insight_catchup_after_hours + 1
    if age_hours >= settings.insight_catchup_after_hours:
        _enqueue_insights(f"catch-up: last run {age_hours:.1f}h ago")


def _nightly_insights() -> None:
    _enqueue_insights("nightly cron")


def _nightly_study() -> None:
    _enqueue_study("nightly study cron")


def start(scheduler: AsyncIOScheduler | None = None) -> AsyncIOScheduler:
    """Start the scheduler (idempotent) — called from the FastAPI lifespan."""
    global _scheduler
    settings = get_settings()
    sched = scheduler or AsyncIOScheduler()
    run_date = datetime.now(timezone.utc) + timedelta(seconds=_CATCHUP_DELAY_SECONDS)
    sched.add_job(_catchup_check, "date", run_date=run_date, id="insight_catchup", replace_existing=True)
    sched.add_job(
        _nightly_insights,
        CronTrigger(hour=settings.insight_cron_hour, minute=0),
        id="insight_nightly",
        replace_existing=True,
    )
    sched.add_job(
        _nightly_study,
        CronTrigger(hour=settings.study_cron_hour, minute=15),
        id="study_nightly",
        replace_existing=True,
    )
    # Sunday 06:00 local-ish UTC — board pack for the week
    sched.add_job(
        _weekly_digest,
        CronTrigger(day_of_week="sun", hour=settings.digest_cron_hour, minute=0),
        id="digest_weekly",
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
