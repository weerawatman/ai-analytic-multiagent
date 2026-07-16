"""Consultant wiring through job runner + API."""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from backend.app.agents.state import AgentState
from backend.app.services import chat_store, consultant_service, job_runner, job_store
from backend.app.services.team_memory_store import (
    empty_team_memory,
    load_team_memory,
    save_team_memory,
)


class FakeSnapshot:
    def __init__(self, values: dict) -> None:
        self.values = values
        self.next = ()


class FakeGraph:
    def __init__(self, final_state: dict):
        self.final_state = final_state

    async def astream(self, input_state, config=None, stream_mode=None):
        human = HumanMessage(content="q")
        de_msg = AIMessage(content="DE ok", name="data_engineer")
        yield ("values", {"messages": [human]})
        yield ("updates", {"de_context": {"messages": [de_msg], "schema_info": "ok"}})
        yield ("values", {"messages": [human, de_msg]})

    async def aget_state(self, config):
        return FakeSnapshot(self.final_state)


def _final_state(answer: str = "คำตอบฐาน") -> dict:
    return AgentState(
        thread_id="t-consult",
        current_agent="business_analyst",
        final_answer=answer,
        quality_payload={
            "agents_involved": ["data_engineer", "data_analyst"],
            "quality_gaps": [],
        },
    ).model_dump()


async def _poll(client: AsyncClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        response = await client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] not in ("queued", "running"):
            return job
        assert asyncio.get_event_loop().time() < deadline
        await asyncio.sleep(0.02)


@pytest.mark.anyio
async def test_chat_review_appends_consultant(
    client: AsyncClient, temp_storage, consultant_enabled, monkeypatch
):
    job_store.init_jobs_db()
    monkeypatch.setattr(job_runner, "graph", FakeGraph(_final_state()))

    async def fake_review(*args, **kwargs):
        return "ควรตรวจนิยามยอดขาย"

    monkeypatch.setattr(consultant_service, "should_review", lambda state: True)
    monkeypatch.setattr(consultant_service, "review_answer", fake_review)

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-rev", "message": "ถาม", "mode": "explore"},
    )
    assert response.status_code == 202
    job = await _poll(client, response.json()["job_id"])
    assert job["status"] == "done"
    assert "ความเห็นที่ปรึกษา (Claude)" in job["result"]["content"]
    steps = {p["step"]: p["status"] for p in job["progress"]}
    assert steps.get("consultant_review") == "done"

    messages = chat_store.get_messages("t-rev")
    consultant_msgs = [m for m in messages if m.get("agent") == "consultant"]
    assert len(consultant_msgs) == 1
    assert "ควรตรวจนิยามยอดขาย" in consultant_msgs[0]["content"]


@pytest.mark.anyio
async def test_chat_review_none_still_done(
    client: AsyncClient, temp_storage, consultant_enabled, monkeypatch
):
    job_store.init_jobs_db()
    monkeypatch.setattr(job_runner, "graph", FakeGraph(_final_state("คำตอบครบ")))

    async def fake_review(*args, **kwargs):
        return None

    monkeypatch.setattr(consultant_service, "should_review", lambda state: True)
    monkeypatch.setattr(consultant_service, "review_answer", fake_review)

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-skip", "message": "ถาม", "mode": "explore"},
    )
    job = await _poll(client, response.json()["job_id"])
    assert job["status"] == "done"
    assert job["result"]["content"] == "คำตอบครบ"
    steps = {p["step"]: p["status"] for p in job["progress"]}
    assert steps.get("consultant_review") == "failed"


@pytest.mark.anyio
async def test_consult_endpoint_503_when_disabled(client: AsyncClient, temp_storage, monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENABLED", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    response = await client.post(
        "/api/v1/consultant/theme-x/consult",
        json={"question": "ช่วยดูทีมหน่อย"},
    )
    assert response.status_code == 503
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_consult_job_done_and_409(
    client: AsyncClient, temp_storage, consultant_enabled, monkeypatch
):
    job_store.init_jobs_db()
    save_team_memory(empty_team_memory("theme-c", "ยอดขาย"))

    async def fake_answer(theme_id, question):
        from backend.app.services.team_memory_store import append_consultant_note

        append_consultant_note(theme_id, f"advice:{question}")
        return f"advice:{question}"

    monkeypatch.setattr(consultant_service, "answer_question", fake_answer)

    first = await client.post(
        "/api/v1/consultant/theme-c/consult",
        json={"question": "ทีมควรปรับปรุงอย่างไร"},
    )
    assert first.status_code == 202
    job_id = first.json()["job_id"]

    # Simulate active job for 409
    gate = asyncio.Event()

    async def slow_answer(theme_id, question):
        await gate.wait()
        return "slow"

    # Start a second consult after first finishes
    job = await _poll(client, job_id)
    assert job["status"] == "done"
    assert "advice:" in job["result"]["advice"]
    mem = load_team_memory("theme-c")
    assert mem and mem.get("consultant_notes")

    # 409 while running
    monkeypatch.setattr(consultant_service, "answer_question", slow_answer)
    running = await client.post(
        "/api/v1/consultant/theme-c/consult",
        json={"question": "q2"},
    )
    assert running.status_code == 202
    second = await client.post(
        "/api/v1/consultant/theme-c/consult",
        json={"question": "q3"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["job_id"] == running.json()["job_id"]
    gate.set()
    await _poll(client, running.json()["job_id"])


@pytest.mark.anyio
async def test_onboarding_coach_timeline(
    client: AsyncClient, temp_storage, consultant_enabled, monkeypatch
):
    job_store.init_jobs_db()
    disc_dir = temp_storage / "knowledge" / "themes" / "theme-ob"
    disc_dir.mkdir(parents=True)
    (disc_dir / "discovery.json").write_text(
        json.dumps({"theme_id": "theme-ob", "profiles": [], "relationships": []}),
        encoding="utf-8",
    )

    async def fake_onboarding(theme_id, theme_name=""):
        return {"theme_id": theme_id, "status": "completed"}

    async def fake_coach(theme_id, theme_name):
        return None  # unavailable — job still done

    monkeypatch.setattr(job_runner, "run_onboarding", fake_onboarding)
    monkeypatch.setattr(consultant_service, "is_enabled", lambda mode: mode == "coach_onboarding")
    monkeypatch.setattr(consultant_service, "coach_team", fake_coach)

    response = await client.post("/api/v1/onboarding/theme-ob/run?theme_name=ยอดขาย")
    assert response.status_code == 202
    job = await _poll(client, response.json()["job_id"])
    assert job["status"] == "done"
    steps = {p["step"]: p["status"] for p in job["progress"]}
    assert steps.get("onboarding") == "done"
    assert steps.get("consultant_coach") == "failed"
