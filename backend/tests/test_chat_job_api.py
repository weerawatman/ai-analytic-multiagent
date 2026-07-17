"""Job-based chat API: submit → poll → done, incremental persistence, 409, failure."""

import asyncio

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from backend.app.agents.state import AgentState
from backend.app.services import chat_store, job_store, job_runner


class FakeSnapshot:
    def __init__(self, values: dict, next_: tuple = ()) -> None:
        self.values = values
        self.next = next_


class FakeGraph:
    """Streams (mode, chunk) tuples like the real graph with stream_mode=["updates", "values"]."""

    def __init__(self, final_state: dict, gate: asyncio.Event | None = None, error: Exception | None = None):
        self.final_state = final_state
        self.gate = gate
        self.error = error

    async def astream(self, input_state, config=None, stream_mode=None):
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        human = HumanMessage(content="q")
        de_msg = AIMessage(content="DE: โครงสร้างตาราง", name="data_engineer")
        da_msg = AIMessage(content="DA: SQL + ผลลัพธ์", name="data_analyst")
        yield ("values", {"messages": [human]})
        yield (
            "updates",
            {"de_context": {"messages": [de_msg], "schema_info": "โครงสร้างตาราง"}},
        )
        yield ("values", {"messages": [human, de_msg]})
        yield (
            "updates",
            {
                "data_analyst": {
                    "messages": [da_msg],
                    "query_result": "DA: SQL + ผลลัพธ์",
                    "step_errors": [],
                }
            },
        )
        yield ("values", {"messages": [human, de_msg, da_msg]})

    async def aget_state(self, config):
        return FakeSnapshot(self.final_state)


def _final_state(answer: str = "คำตอบสุดท้ายจากทีม") -> dict:
    return AgentState(
        thread_id="t-job",
        current_agent="business_analyst",
        final_answer=answer,
        quality_payload={"agents_involved": ["data_engineer", "data_analyst"], "quality_gaps": []},
    ).model_dump()


async def _poll_until_done(client: AsyncClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        response = await client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] not in ("queued", "running"):
            return job
        assert asyncio.get_event_loop().time() < deadline, "job never finished"
        await asyncio.sleep(0.02)


async def test_chat_submit_and_poll_done(client: AsyncClient, temp_storage, monkeypatch):
    job_store.init_jobs_db()
    monkeypatch.setattr(job_runner, "graph", FakeGraph(_final_state()))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-job", "message": "ยอดขายปีนี้เท่าไหร่", "mode": "explore"},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job = await _poll_until_done(client, job_id)
    assert job["status"] == "done"
    assert job["result"]["content"] == "คำตอบสุดท้ายจากทีม"
    assert job["result"]["agent"] == "ai_data_team"

    steps = {p["step"]: p["status"] for p in job["progress"]}
    assert steps.get("de_context") == "done"
    assert steps.get("data_analyst") == "done"

    # Incremental persistence: user + per-agent + final answer all in SQLite
    messages = chat_store.get_messages("t-job")
    contents = [m["content"] for m in messages]
    assert "ยอดขายปีนี้เท่าไหร่" in contents
    assert "DE: โครงสร้างตาราง" in contents
    assert "DA: SQL + ผลลัพธ์" in contents
    assert "คำตอบสุดท้ายจากทีม" in contents
    agents = {m["agent"] for m in messages if m["role"] == "assistant"}
    assert {"data_engineer", "data_analyst", "ai_data_team"} <= agents


async def test_duplicate_submit_returns_409_with_job_id(client: AsyncClient, temp_storage, monkeypatch):
    job_store.init_jobs_db()
    gate = asyncio.Event()
    monkeypatch.setattr(job_runner, "graph", FakeGraph(_final_state(), gate=gate))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    first = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-dup", "message": "คำถามแรก", "mode": "explore"},
    )
    assert first.status_code == 202
    first_job_id = first.json()["job_id"]

    second = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-dup", "message": "คำถามซ้ำ", "mode": "explore"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["job_id"] == first_job_id

    gate.set()
    job = await _poll_until_done(client, first_job_id)
    assert job["status"] == "done"


async def test_failing_graph_marks_job_failed(client: AsyncClient, temp_storage, monkeypatch):
    job_store.init_jobs_db()
    monkeypatch.setattr(
        job_runner, "graph", FakeGraph(_final_state(), error=RuntimeError("Ollama down"))
    )
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-fail", "message": "คำถาม", "mode": "explore"},
    )
    assert response.status_code == 202
    job = await _poll_until_done(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "Ollama down" in job["error"]


async def test_job_endpoints_not_found(client: AsyncClient, temp_storage):
    job_store.init_jobs_db()
    assert (await client.get("/api/v1/jobs/missing")).status_code == 404
    assert (await client.post("/api/v1/jobs/missing/cancel")).status_code == 404


async def test_onboarding_submit_requires_discovery(client: AsyncClient, temp_storage):
    job_store.init_jobs_db()
    response = await client.post("/api/v1/onboarding/no-such-theme/run")
    assert response.status_code == 400
    assert "discovery" in response.json()["detail"].lower()


class SlowGraph(FakeGraph):
    """Hangs until cancelled / timed out — used to exercise chat_job_max_seconds."""

    async def astream(self, input_state, config=None, stream_mode=None):
        await asyncio.sleep(3600)
        if False:  # pragma: no cover — make this an async generator
            yield ("values", {})


async def test_chat_job_wall_clock_timeout(client: AsyncClient, temp_storage, monkeypatch):
    job_store.init_jobs_db()
    monkeypatch.setenv("CHAT_JOB_MAX_SECONDS", "1")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(job_runner, "graph", SlowGraph(_final_state()))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-timeout", "message": "คำถามช้า", "mode": "explore"},
    )
    assert response.status_code == 202
    job = await _poll_until_done(client, response.json()["job_id"], timeout=10.0)
    assert job["status"] == "failed"
    assert "wall-clock" in job["error"].lower() or "1200" in job["error"] or "limit" in job["error"].lower()
    get_settings.cache_clear()


async def test_chat_job_graceful_sql_failed_result(client: AsyncClient, temp_storage, monkeypatch):
    """Final answer after exhausted SQL retries must be polite Thai — not raw traceback."""
    from backend.app.services.quality_assembly import SQL_FAILED_CEO_MSG_TH

    job_store.init_jobs_db()
    final = AgentState(
        thread_id="t-grace",
        current_agent="business_analyst",
        sql_failed=True,
        sql_retry_count=3,
        sql_error="ชื่อคอลัมน์ผิด",
        final_answer=f"🟡 Draft\n\n### สถานะ SQL\n⚠️ {SQL_FAILED_CEO_MSG_TH}\n",
        ba_summary=f"BUSINESS_SUMMARY:\n{SQL_FAILED_CEO_MSG_TH}",
        quality_payload={
            "agents_involved": ["data_analyst", "business_analyst"],
            "quality_gaps": [],
            "sql_failed": True,
            "answer_summary_th": SQL_FAILED_CEO_MSG_TH,
        },
    ).model_dump()
    monkeypatch.setattr(job_runner, "graph", FakeGraph(final))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-grace", "message": "ยอดขายทั้งตาราง", "mode": "explore"},
    )
    assert response.status_code == 202
    job = await _poll_until_done(client, response.json()["job_id"])
    assert job["status"] == "done"
    content = job["result"]["content"]
    assert "ลองปรับ SQL แล้ว 3 ครั้ง" in content
    assert "Traceback" not in content
    assert "SQL_ERROR:" not in content
