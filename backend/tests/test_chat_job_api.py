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
    # User-facing error keeps the exception type only; detail stays in the log.
    assert "RuntimeError" in job["error"]
    assert "Ollama down" not in job["error"]


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
    assert "เกินกำหนด" in job["error"]
    assert "เกินเวลาที่กำหนดของงาน" in job["error"]
    assert "wall-clock" not in job["error"].lower()
    get_settings.cache_clear()


async def test_chat_job_consultant_review_timeout_continues(
    client: AsyncClient, temp_storage, monkeypatch
):
    """A hung consultant (Claude) call must not stall the job — the step is
    marked failed after its own bounded timeout and the answer still ships."""
    job_store.init_jobs_db()
    # Consultant budget in job_runner = consultant_timeout + 30 → 1s here.
    monkeypatch.setenv("CONSULTANT_TIMEOUT", "-29")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(job_runner, "graph", FakeGraph(_final_state()))
    monkeypatch.setattr(
        "backend.app.services.consultant_service.should_review", lambda state: True
    )

    async def hung_review(*args, **kwargs):
        await asyncio.sleep(3600)

    monkeypatch.setattr(
        "backend.app.services.consultant_service.review_answer", hung_review
    )

    response = await client.post(
        "/api/v1/chat/",
        json={"thread_id": "t-consult-hang", "message": "ยอดขาย", "mode": "explore"},
    )
    assert response.status_code == 202
    job = await _poll_until_done(client, response.json()["job_id"], timeout=10.0)
    assert job["status"] == "done"
    assert job["result"]["content"] == "คำตอบสุดท้ายจากทีม"
    review_steps = [p for p in job["progress"] if p["step"] == "consultant_review"]
    assert review_steps and review_steps[-1]["status"] == "failed"
    note = review_steps[-1].get("note") or ""
    assert "เกินเวลา" in note
    assert "ข้าม" in note
    assert "timed out" not in note.lower()
    get_settings.cache_clear()


def test_persist_new_messages_sanitizes_da_failed_attempts(temp_storage):
    """Mid-stream persisted DA messages must not leak exception/ODBC details."""
    from backend.app.agents.data_analyst import SQL_FAILED_SUMMARY_TH
    from backend.app.schemas.chat import ChatRequest

    request = ChatRequest(thread_id="t-sanitize", message="ยอดขาย", mode="explore")
    da_fail = AIMessage(
        content=(
            "ANALYSIS: draft วิเคราะห์ยอดขาย\n\n"
            "SQL_ATTEMPT_FAILED: รัน SQL ไม่สำเร็จ (ProgrammingError: ('42000', "
            "'[42000] [Microsoft][ODBC Driver 18 for SQL Server]...'))\n\n"
            "SQL_ATTEMPT_FAILED: รัน SQL ไม่สำเร็จ (OperationalError: timeout)\n\n"
            + SQL_FAILED_SUMMARY_TH
        ),
        name="data_analyst",
    )
    ba_msg = AIMessage(content="BA: สรุปเชิงธุรกิจ", name="business_analyst")

    count = job_runner._persist_new_messages(
        request, [HumanMessage(content="ยอดขาย"), da_fail, ba_msg], 0
    )
    assert count == 3

    messages = chat_store.get_messages("t-sanitize")
    da_persisted = [m["content"] for m in messages if m["agent"] == "data_analyst"]
    assert len(da_persisted) == 1
    body = da_persisted[0]
    # Analytic portion + final graceful summary intact; attempts noted politely.
    assert "ANALYSIS: draft วิเคราะห์ยอดขาย" in body
    assert SQL_FAILED_SUMMARY_TH in body
    assert "[รอบที่ 1] SQL ยังไม่ผ่าน" in body
    assert "[รอบที่ 2] SQL ยังไม่ผ่าน" in body
    for banned in (
        "SQL_ATTEMPT_FAILED",
        "ProgrammingError",
        "OperationalError",
        "ODBC",
        "42000",
        "Traceback",
    ):
        assert banned not in body
    # Non-DA messages pass through untouched.
    ba_persisted = [m["content"] for m in messages if m["agent"] == "business_analyst"]
    assert ba_persisted == ["BA: สรุปเชิงธุรกิจ"]


def test_record_step_sanitizes_progress_note(temp_storage):
    """Step notes are rendered in the progress UI — no ODBC/exception detail."""
    job_store.init_jobs_db()
    job = job_store.create_job("chat", "t-note")
    job_store.append_step(job["id"], "data_analyst")
    job_runner._record_step(
        job["id"],
        "data_analyst",
        {
            "step_errors": [
                "data_analyst SQL: รัน SQL ไม่สำเร็จ (ProgrammingError: ('42000', "
                "'[42000] [Microsoft][ODBC Driver 18 for SQL Server]...'))"
            ]
        },
        "explore",
    )
    entry = [p for p in job_store.get_job(job["id"])["progress"] if p["step"] == "data_analyst"][-1]
    assert entry["status"] == "failed"
    note = entry["note"]
    assert "data_analyst SQL" in note
    assert "ProgrammingError" in note  # exception type stays for context
    for banned in ("ODBC", "42000", "Microsoft", "Traceback"):
        assert banned not in note


def test_record_step_keeps_clean_thai_note(temp_storage):
    """Already-friendly Thai errors (e.g. row-count guidance) pass through."""
    job_store.init_jobs_db()
    job = job_store.create_job("chat", "t-note-th")
    job_store.append_step(job["id"], "data_analyst")
    friendly = "data_analyst SQL: จำนวนแถวโดยประมาณ 99,999 เกินเกณฑ์ 50,000 — กรุณาจำกัดด้วย WHERE"
    job_runner._record_step(job["id"], "data_analyst", {"step_errors": [friendly]}, "explore")
    entry = [p for p in job_store.get_job(job["id"])["progress"] if p["step"] == "data_analyst"][-1]
    assert entry["note"] == friendly


async def _poll_store_until_done(job_id: str, timeout: float = 10.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        job = job_store.get_job(job_id)
        assert job is not None
        if job["status"] not in ("queued", "running"):
            return job
        assert asyncio.get_event_loop().time() < deadline, "job never finished"
        await asyncio.sleep(0.02)


async def test_onboarding_job_wall_clock_timeout(temp_storage, monkeypatch):
    """Mirrors test_chat_job_wall_clock_timeout for the onboarding job."""
    job_store.init_jobs_db()
    monkeypatch.setenv("ONBOARDING_JOB_MAX_SECONDS", "1")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    async def hung_onboarding(theme_id, theme_name=""):
        await asyncio.sleep(3600)

    monkeypatch.setattr(job_runner, "run_onboarding", hung_onboarding)

    job = job_runner.start_onboarding_job("theme-slow", "ยอดขาย")
    job = await _poll_store_until_done(job["id"])
    assert job["status"] == "failed"
    assert "เกินกำหนด" in job["error"]
    assert "เกินเวลาที่กำหนดของงาน" in job["error"]
    assert "wall-clock" not in job["error"].lower()
    steps = [p for p in job["progress"] if p["step"] == "onboarding"]
    assert steps and steps[-1]["status"] == "failed"
    assert job["current_step"] is None
    get_settings.cache_clear()


async def test_onboarding_job_timeout_during_coach(temp_storage, monkeypatch):
    """Wall-clock cap must also fire while consultant_coach is hanging."""
    from backend.app.services import consultant_service

    job_store.init_jobs_db()
    monkeypatch.setenv("ONBOARDING_JOB_MAX_SECONDS", "1")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    async def fast_onboarding(theme_id, theme_name=""):
        return {"theme_id": theme_id, "status": "completed"}

    async def hung_coach(theme_id, theme_name=""):
        await asyncio.sleep(3600)

    monkeypatch.setattr(job_runner, "run_onboarding", fast_onboarding)
    monkeypatch.setattr(
        consultant_service, "is_enabled", lambda mode: mode == "coach_onboarding"
    )
    monkeypatch.setattr(consultant_service, "coach_team", hung_coach)

    job = job_runner.start_onboarding_job("theme-coach-hang", "ยอดขาย")
    job = await _poll_store_until_done(job["id"])
    assert job["status"] == "failed"
    assert "เกินกำหนด" in job["error"]
    assert "เกินเวลาที่กำหนดของงาน" in job["error"]
    coach_steps = [p for p in job["progress"] if p["step"] == "consultant_coach"]
    assert coach_steps and coach_steps[-1]["status"] == "failed"
    assert job["current_step"] is None
    get_settings.cache_clear()


async def test_consult_job_wall_clock_timeout(temp_storage, monkeypatch):
    """A hung Claude call must not stall the consult job past its bound
    (consultant_timeout + 30) — mirrors the consultant review step behavior."""
    job_store.init_jobs_db()
    monkeypatch.setenv("CONSULTANT_TIMEOUT", "-29")  # bound = -29 + 30 = 1s
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    async def hung_answer(theme_id, question):
        await asyncio.sleep(3600)

    monkeypatch.setattr(
        "backend.app.services.consultant_service.answer_question", hung_answer
    )

    job = job_runner.start_consult_job("theme-consult-slow", "ช่วยดูทีมหน่อย")
    job = await _poll_store_until_done(job["id"])
    assert job["status"] == "failed"
    assert "เกินกำหนด" in job["error"]
    assert "เกินเวลาที่กำหนดของงาน" in job["error"]
    assert "wall-clock" not in job["error"].lower()
    steps = [p for p in job["progress"] if p["step"] == "consult"]
    assert steps and steps[-1]["status"] == "failed"
    assert job["current_step"] is None
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
