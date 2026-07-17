"""Deep-onboarding job API — submit, poll to terminal, homework/starter GETs."""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient

from backend.app.services import job_runner, job_store


@pytest.fixture
def theme_ready(temp_storage):
    theme_id = "deep-theme"
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True, exist_ok=True)
    (discovery_dir / "discovery.json").write_text(
        json.dumps(
            {
                "theme_id": theme_id,
                "discovered_at": "2026-07-17T12:00:00+00:00",
                "profiles": [
                    {
                        "table": "SAPHANADB.CE1SATG_All_Cleaned",
                        "table_name": "CE1SATG_All_Cleaned",
                        "row_count": 1_000_000,
                        "columns": [
                            {"COLUMN_NAME": "SourceMonth", "DATA_TYPE": "varchar"},
                            {"COLUMN_NAME": "Revenue", "DATA_TYPE": "decimal"},
                        ],
                    }
                ],
                "relationships": [],
            }
        ),
        encoding="utf-8",
    )
    return theme_id


async def _poll(client: AsyncClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        if job["status"] not in ("queued", "running"):
            return job
        assert asyncio.get_event_loop().time() < deadline, "job never finished"
        await asyncio.sleep(0.02)


async def test_deep_run_completes_and_persists(client: AsyncClient, theme_ready, monkeypatch):
    job_store.init_jobs_db()
    # Offline: deterministic, no live SQL — still must produce artifacts.
    monkeypatch.setattr(
        "backend.app.services.deep_profile_service.get_active_sql_source", lambda: "offline"
    )
    monkeypatch.setattr(
        "backend.app.services.insight_starter_service.get_active_sql_source", lambda: "offline"
    )

    response = await client.post(f"/api/v1/onboarding/{theme_ready}/deep-run?theme_name=Saphanadb")
    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "deep_onboarding"

    job = await _poll(client, body["job_id"])
    assert job["status"] == "done"
    steps = {p["step"]: p["status"] for p in job["progress"]}
    assert steps.get("deep_profile") == "done"
    assert steps.get("starter_pack") == "done"
    assert job["result"]["homework"]["evidence_level"] == "disk_cache"

    hw = await client.get(f"/api/v1/onboarding/{theme_ready}/homework")
    assert hw.status_code == 200
    assert hw.json()["table_roles"]["SAPHANADB.CE1SATG_All_Cleaned"] == "fact"

    pack = await client.get(f"/api/v1/onboarding/{theme_ready}/starter-pack")
    assert pack.status_code == 200
    assert pack.json()["theme_id"] == theme_ready


async def test_deep_run_requires_discovery(client: AsyncClient, temp_storage):
    job_store.init_jobs_db()
    response = await client.post("/api/v1/onboarding/nope/deep-run")
    assert response.status_code == 400


async def test_deep_run_conflict_returns_409(client: AsyncClient, theme_ready, monkeypatch):
    job_store.init_jobs_db()
    gate = asyncio.Event()

    async def slow_steps(job_id, theme_id, theme_name):
        await gate.wait()
        return {}

    monkeypatch.setattr(job_runner, "_run_deep_profile_steps", slow_steps)

    first = await client.post(f"/api/v1/onboarding/{theme_ready}/deep-run")
    assert first.status_code == 202
    second = await client.post(f"/api/v1/onboarding/{theme_ready}/deep-run")
    assert second.status_code == 409
    assert second.json()["detail"]["job_id"] == first.json()["job_id"]
    gate.set()
    await _poll(client, first.json()["job_id"])


async def test_homework_endpoints_404_when_absent(client: AsyncClient, temp_storage):
    assert (await client.get("/api/v1/onboarding/none/homework")).status_code == 404
    assert (await client.get("/api/v1/onboarding/none/starter-pack")).status_code == 404


async def test_profile_failure_does_not_block_job(client: AsyncClient, theme_ready, monkeypatch):
    """Homework step failure is recorded but the job still terminates cleanly."""
    job_store.init_jobs_db()

    def broken_homework(theme_id, theme_name=""):
        raise RuntimeError("profiling exploded")

    monkeypatch.setattr(
        "backend.app.services.deep_profile_service.build_homework", broken_homework
    )
    monkeypatch.setattr(
        "backend.app.services.insight_starter_service.get_active_sql_source", lambda: "offline"
    )

    response = await client.post(f"/api/v1/onboarding/{theme_ready}/deep-run")
    job = await _poll(client, response.json()["job_id"])
    assert job["status"] == "done"
    steps = {p["step"]: p for p in job["progress"]}
    assert steps["deep_profile"]["status"] == "failed"
    assert "RuntimeError" in (steps["deep_profile"]["note"] or "")
    assert "profiling exploded" not in (steps["deep_profile"]["note"] or "")
    assert steps["starter_pack"]["status"] == "done"
