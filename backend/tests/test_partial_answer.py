"""Chat-job timeout must ship a labeled partial answer, never a silent blank."""

from __future__ import annotations

import asyncio

from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from backend.app.agents.state import AgentState
from backend.app.services import chat_store, job_runner, job_store
from backend.app.services.job_runner import build_partial_answer


def _state(**kwargs) -> AgentState:
    defaults = dict(
        messages=[HumanMessage(content="ขอ Gross Profit 6 เดือน")],
        thread_id="t-partial",
    )
    defaults.update(kwargs)
    return AgentState(**defaults)


def test_build_partial_answer_with_de_and_ds():
    state = _state(
        schema_info="DE: CE1SATG_All_Cleaned เป็น fact 1.6M แถว",
        analysis_summary="DS: HYPOTHESES แนวโน้มรายเดือน",
        generated_sql="SELECT SourceMonth FROM t",
    )
    answer = build_partial_answer(state, 1200)
    assert answer is not None
    assert "คำตอบบางส่วน" in answer
    assert "1200" in answer
    assert "Data Engineer" in answer
    assert "Data Scientist" in answer
    assert "Draft SQL" in answer
    assert "ขั้นตอนถัดไป" in answer


def test_build_partial_answer_strips_failed_attempt_lines():
    state = _state(
        query_result="ANALYSIS: draft\n\nSQL_ATTEMPT_FAILED: รายละเอียด ODBC ห้ามโชว์",
        sql_source="fabric",
    )
    answer = build_partial_answer(state, 1200)
    assert answer is not None
    assert "SQL_ATTEMPT_FAILED" not in answer
    assert "ODBC ห้ามโชว์" not in answer
    assert "แหล่งข้อมูล" in answer


def test_build_partial_answer_none_when_nothing_done():
    assert build_partial_answer(_state(), 1200) is None


class FakeSnapshot:
    def __init__(self, values: dict) -> None:
        self.values = values


class HangingGraphWithState:
    """astream hangs (forces timeout); aget_state returns mid-run checkpoint."""

    def __init__(self, values: dict) -> None:
        self.values = values

    async def astream(self, input_state, config=None, stream_mode=None):
        await asyncio.sleep(3600)
        if False:  # pragma: no cover
            yield ("values", {})

    async def aget_state(self, config):
        return FakeSnapshot(self.values)


async def _poll(client: AsyncClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        if job["status"] not in ("queued", "running"):
            return job
        assert asyncio.get_event_loop().time() < deadline
        await asyncio.sleep(0.02)


async def test_timeout_ships_partial_answer(client: AsyncClient, temp_storage, monkeypatch):
    job_store.init_jobs_db()
    monkeypatch.setenv("CHAT_JOB_MAX_SECONDS", "1")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    question = "ขอ Gross Profit รายเดือน"
    mid_state = AgentState(
        messages=[
            HumanMessage(content=question),
            AIMessage(content="DE done", name="data_engineer"),
        ],
        thread_id="t-partial-job",
        schema_info="DE: โครงสร้าง CE1SATG (fact, 1.6M แถว)",
        analysis_summary="DS: plan แนวโน้มรายเดือน",
    ).model_dump()
    monkeypatch.setattr(job_runner, "graph", HangingGraphWithState(mid_state))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-partial-job", "message": question, "mode": "explore"},
    )
    assert response.status_code == 202
    job = await _poll(client, response.json()["job_id"])

    # Terminal + useful: done with a partial answer instead of a bare failure.
    assert job["status"] == "done"
    assert job["result"]["partial"] is True
    content = job["result"]["content"]
    assert "คำตอบบางส่วน" in content
    assert "CE1SATG" in content

    # Partial answer also lands in persisted chat history for the thread.
    messages = chat_store.get_messages("t-partial-job")
    assert any("คำตอบบางส่วน" in m["content"] for m in messages)
    get_settings.cache_clear()


async def test_timeout_with_stale_state_still_fails_cleanly(
    client: AsyncClient, temp_storage, monkeypatch
):
    """Checkpoint from a previous question must not leak into this answer."""
    job_store.init_jobs_db()
    monkeypatch.setenv("CHAT_JOB_MAX_SECONDS", "1")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    stale_state = AgentState(
        messages=[HumanMessage(content="คำถามเก่า คนละเรื่อง")],
        thread_id="t-stale",
        schema_info="ข้อมูลของคำถามเก่า",
    ).model_dump()
    monkeypatch.setattr(job_runner, "graph", HangingGraphWithState(stale_state))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: False
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-stale", "message": "คำถามใหม่", "mode": "explore"},
    )
    job = await _poll(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "เกินกำหนด" in job["error"]
    # Stale content must not have been persisted as an answer.
    messages = chat_store.get_messages("t-stale")
    assert not any("ข้อมูลของคำถามเก่า" in m["content"] for m in messages)
    get_settings.cache_clear()
