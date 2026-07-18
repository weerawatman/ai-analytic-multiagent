"""Insight pipeline scheduler tests (Phase I) — offline, mocked job_runner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.services import job_store, scheduler_service


@pytest.fixture
def jobs_db(temp_storage):
    job_store.init_jobs_db()
    return temp_storage


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("INSIGHT_PIPELINE_ENABLED", "true")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_ollama_busy_true_when_chat_running(jobs_db):
    job = job_store.create_job("chat", "t1", question="hi")
    job_store.update_job(job["id"], status="running")
    assert scheduler_service._ollama_busy() is True


def test_ollama_busy_false_when_idle(jobs_db):
    assert scheduler_service._ollama_busy() is False


def test_enqueue_skipped_when_disabled(jobs_db, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    scheduler_service._enqueue_insights("test")
    assert calls == []


def test_enqueue_deferred_when_busy(jobs_db, enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    job = job_store.create_job("chat", "t1", question="hi")
    job_store.update_job(job["id"], status="running")
    scheduler_service._enqueue_insights("test")
    assert calls == []


def test_enqueue_runs_when_enabled_and_idle(jobs_db, enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    scheduler_service._enqueue_insights("test")
    assert len(calls) == 1


def test_enqueue_skips_when_already_active(jobs_db, enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    job_store.create_job("insight_pipeline", "analytics:insight_pipeline", question="x")
    scheduler_service._enqueue_insights("test")
    assert calls == []


def test_catchup_check_enqueues_when_never_run(jobs_db, enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    scheduler_service._catchup_check()
    assert len(calls) == 1


def test_catchup_check_skips_when_recently_done(jobs_db, enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    job = job_store.create_job("insight_pipeline", "analytics:insight_pipeline", question="x")
    job_store.update_job(
        job["id"], status="done", finished_at=datetime.now(timezone.utc).isoformat()
    )
    scheduler_service._catchup_check()
    assert calls == []


def test_catchup_check_enqueues_when_stale(jobs_db, enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        scheduler_service.job_runner, "start_insight_pipeline_job", lambda **kw: calls.append(kw)
    )
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    job = job_store.create_job("insight_pipeline", "analytics:insight_pipeline", question="x")
    job_store.update_job(job["id"], status="done", finished_at=old)
    scheduler_service._catchup_check()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_start_and_shutdown_idempotent():
    sched = scheduler_service.start()
    assert sched.running
    scheduler_service.start(sched)  # idempotent — same scheduler, no crash
    scheduler_service.shutdown()
    assert scheduler_service._scheduler is None


def test_inv6_smoke_no_thread_or_subprocess_imports():
    text = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "scheduler_service.py"
    ).read_text(encoding="utf-8")
    for banned in ("import threading", "import multiprocessing", "import subprocess"):
        assert banned not in text
    assert "job_runner" in text
