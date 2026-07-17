"""Job store CRUD, timeline, and orphan reconciliation."""

from backend.app.services import job_store


def _init(temp_storage):
    job_store.init_jobs_db()


def test_create_and_get_job(temp_storage):
    _init(temp_storage)
    job = job_store.create_job("chat", "t1", question="ยอดขายปีนี้", params={"mode": "explore"})
    assert job["status"] == "queued"
    assert job["kind"] == "chat"
    assert job["params"] == {"mode": "explore"}
    assert job["progress"] == []

    fetched = job_store.get_job(job["id"])
    assert fetched is not None
    assert fetched["question"] == "ยอดขายปีนี้"
    assert job_store.get_job("missing") is None


def test_update_job_serializes_result(temp_storage):
    _init(temp_storage)
    job = job_store.create_job("chat", "t1")
    job_store.update_job(job["id"], status="done", result={"content": "คำตอบ", "agent": "ai_data_team"})
    fetched = job_store.get_job(job["id"])
    assert fetched["status"] == "done"
    assert fetched["result"]["content"] == "คำตอบ"


def test_step_timeline(temp_storage):
    _init(temp_storage)
    job = job_store.create_job("chat", "t1")
    job_store.append_step(job["id"], "data_analyst")
    fetched = job_store.get_job(job["id"])
    assert fetched["current_step"] == "data_analyst"
    assert fetched["progress"][0]["status"] == "running"

    job_store.finish_step(job["id"], "data_analyst", "done")
    fetched = job_store.get_job(job["id"])
    assert fetched["progress"][0]["status"] == "done"
    assert fetched["progress"][0]["ended_at"] is not None

    # finish_step on a step never started creates a closed entry
    job_store.finish_step(job["id"], "business_analyst", "failed", note="LLM timeout")
    fetched = job_store.get_job(job["id"])
    assert fetched["progress"][1]["step"] == "business_analyst"
    assert fetched["progress"][1]["status"] == "failed"
    assert fetched["progress"][1]["note"] == "LLM timeout"


def test_find_active_job(temp_storage):
    _init(temp_storage)
    assert job_store.find_active_job("chat", "t1") is None
    job = job_store.create_job("chat", "t1")
    active = job_store.find_active_job("chat", "t1")
    assert active is not None and active["id"] == job["id"]

    job_store.update_job(job["id"], status="done")
    assert job_store.find_active_job("chat", "t1") is None
    # other kinds / threads unaffected
    assert job_store.find_active_job("onboarding", "t1") is None


def test_list_jobs_filters(temp_storage):
    _init(temp_storage)
    a = job_store.create_job("chat", "t1")
    b = job_store.create_job("onboarding", "theme1")
    job_store.update_job(a["id"], status="done")

    assert {j["id"] for j in job_store.list_jobs()} == {a["id"], b["id"]}
    assert [j["id"] for j in job_store.list_jobs(kind="onboarding")] == [b["id"]]
    assert [j["id"] for j in job_store.list_jobs(active_only=True)] == [b["id"]]
    assert [j["id"] for j in job_store.list_jobs(thread_id="t1")] == [a["id"]]


def test_fail_orphaned_jobs(temp_storage):
    _init(temp_storage)
    running = job_store.create_job("chat", "t1")
    job_store.update_job(running["id"], status="running")
    finished = job_store.create_job("chat", "t2")
    job_store.update_job(finished["id"], status="done")

    count = job_store.fail_orphaned_jobs()
    assert count == 1
    assert job_store.get_job(running["id"])["status"] == "failed"
    assert job_store.get_job(finished["id"])["status"] == "done"


def test_purge_old_terminal_jobs(temp_storage):
    """D6 cleanup — old done/failed jobs purged, active and recent jobs kept."""
    from datetime import datetime, timedelta, timezone

    _init(temp_storage)
    old_done = job_store.create_job("chat", "t-old-done")
    old_failed = job_store.create_job("chat", "t-old-failed")
    recent_done = job_store.create_job("chat", "t-recent")
    still_running = job_store.create_job("chat", "t-running")

    old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    job_store.update_job(old_done["id"], status="done", finished_at=old_ts)
    job_store.update_job(old_failed["id"], status="failed", finished_at=old_ts)
    job_store.update_job(recent_done["id"], status="done")
    job_store.update_job(still_running["id"], status="running")

    purged = job_store.purge_old_terminal_jobs(older_than_days=14)
    assert purged == 2
    assert job_store.get_job(old_done["id"]) is None
    assert job_store.get_job(old_failed["id"]) is None
    assert job_store.get_job(recent_done["id"]) is not None
    assert job_store.get_job(still_running["id"]) is not None

    import pytest

    with pytest.raises(ValueError):
        job_store.purge_old_terminal_jobs(older_than_days=0)
