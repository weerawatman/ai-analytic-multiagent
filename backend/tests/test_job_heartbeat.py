"""Phase G1 — job heartbeat + health enrichment."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services import job_store
from backend.app.services.job_health import STALLED_AFTER_SECONDS, enrich_job_status
from backend.app.services.progress_reporter import note_substep


@pytest.fixture
def jobs_db(temp_storage):
    job_store.init_jobs_db()
    return temp_storage


def test_heartbeat_column_migration_idempotent(jobs_db):
    job_store.init_jobs_db()
    job_store.init_jobs_db()
    job = job_store.create_job("chat", "t1", question="hi")
    assert "heartbeat_at" in job or job.get("heartbeat_at") is None
    job_store.touch_job(job["id"])
    refreshed = job_store.get_job(job["id"])
    assert refreshed is not None
    assert refreshed.get("heartbeat_at")


def test_touch_job_updates_heartbeat(jobs_db):
    job = job_store.create_job("chat", "t2", question="q")
    job_store.touch_job(job["id"])
    a = job_store.get_job(job["id"])["heartbeat_at"]
    job_store.touch_job(job["id"])
    b = job_store.get_job(job["id"])["heartbeat_at"]
    assert a and b
    assert b >= a


def test_enrich_health_working_vs_stalled(jobs_db):
    job = job_store.create_job("chat", "t3", question="q")
    now = datetime.now(timezone.utc)
    job_store.update_job(
        job["id"],
        status="running",
        started_at=now.isoformat(),
        heartbeat_at=now.isoformat(),
    )
    enriched = enrich_job_status(job_store.get_job(job["id"]))
    assert enriched["health"] == "working"
    assert enriched["heartbeat_age_s"] is not None
    assert enriched["heartbeat_age_s"] < STALLED_AFTER_SECONDS

    old = (now - timedelta(seconds=STALLED_AFTER_SECONDS + 5)).isoformat()
    job_store.update_job(job["id"], heartbeat_at=old)
    stalled = enrich_job_status(job_store.get_job(job["id"]))
    assert stalled["health"] == "stalled"


def test_note_substep_updates_running_step(jobs_db):
    job = job_store.create_job("chat", "thread-note", question="q")
    job_store.update_job(job["id"], status="running", started_at=job_store._utc_now())
    job_store.append_step(job["id"], "data_analyst")
    note_substep("thread-note", "SQL รอบที่ 2/3")
    refreshed = job_store.get_job(job["id"])
    assert refreshed["progress"][-1]["note"] == "SQL รอบที่ 2/3"


@pytest.mark.asyncio
async def test_jobs_api_returns_health(client, jobs_db):
    job = job_store.create_job("chat", "api-hb", question="q")
    now = datetime.now(timezone.utc).isoformat()
    job_store.update_job(job["id"], status="running", started_at=now, heartbeat_at=now)
    resp = await client.get(f"/api/v1/jobs/{job['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["health"] == "working"
    assert body["heartbeat_at"]
    assert body["heartbeat_age_s"] is not None


@pytest.mark.asyncio
async def test_mark_running_sets_heartbeat(jobs_db):
    from backend.app.services import job_runner

    job = job_store.create_job("chat", "hb-mark", question="hello")
    job_runner._mark_job_running(job["id"])
    refreshed = job_store.get_job(job["id"])
    assert refreshed["status"] == "running"
    assert refreshed.get("heartbeat_at")
    assert refreshed.get("started_at")


@pytest.mark.asyncio
async def test_heartbeat_loop_touches(jobs_db, monkeypatch):
    from backend.app.services import job_runner

    monkeypatch.setattr(job_runner, "_HEARTBEAT_INTERVAL_S", 0.05)
    job = job_store.create_job("chat", "hb-loop", question="hello")
    job_runner._mark_job_running(job["id"])
    first = job_store.get_job(job["id"])["heartbeat_at"]
    task = asyncio.create_task(job_runner._heartbeat_loop(job["id"]))
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    second = job_store.get_job(job["id"])["heartbeat_at"]
    assert second >= first
