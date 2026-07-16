"""Tests for consultant_service — mocked Anthropic client."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.app.services import consultant_service, knowledge_store
from backend.app.services.team_memory_store import load_team_memory, save_team_memory, empty_team_memory


class _FakeMessages:
    def __init__(self, text: str, raise_exc: Exception | None = None):
        self.text = text
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc:
            raise self.raise_exc
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )


class _FakeClient:
    def __init__(self, text: str = "คำแนะนำจากที่ปรึกษา", raise_exc: Exception | None = None):
        self.messages = _FakeMessages(text, raise_exc)


@pytest.mark.anyio
async def test_disabled_without_key_returns_none(temp_storage, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CONSULTANT_ENABLED", "false")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    consultant_service._client = None

    created = {"n": 0}

    def boom():
        created["n"] += 1
        raise AssertionError("should not create client")

    monkeypatch.setattr(consultant_service, "_get_client", boom)
    result = await consultant_service.review_answer(
        "t1", "sales", "q", "draft", {}, []
    )
    assert result is None
    assert created["n"] == 0
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_audit_jsonl_and_success(temp_storage, consultant_enabled, monkeypatch):
    consultant_service._client = None
    fake = _FakeClient("คำแนะนำจากที่ปรึกษา")
    monkeypatch.setattr(consultant_service, "_get_client", lambda: fake)

    note = await consultant_service.review_answer(
        "t1", "sales", "ยอดขายเท่าไหร่", "draft answer", {"sql_primary": "SELECT 1"}, []
    )
    assert note == "คำแนะนำจากที่ปรึกษา"

    audit = temp_storage / "logs" / "consultant_audit.jsonl"
    assert audit.exists()
    line = json.loads(audit.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["status"] == "ok"
    assert line["payload_sha256"]
    assert "draft answer" in line["payload"]
    assert line["usage"]["input_tokens"] == 10


@pytest.mark.anyio
async def test_client_error_returns_none_and_audits(temp_storage, consultant_enabled, monkeypatch):
    consultant_service._client = None
    fake = _FakeClient(raise_exc=RuntimeError("API down"))
    monkeypatch.setattr(consultant_service, "_get_client", lambda: fake)

    note = await consultant_service.review_answer("t1", "sales", "q", "d", {}, ["err"])
    assert note is None
    audit = temp_storage / "logs" / "consultant_audit.jsonl"
    line = json.loads(audit.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["status"] == "error"
    assert "API down" in line["error"]


@pytest.mark.anyio
async def test_coach_writes_notes_and_drafts(temp_storage, consultant_enabled, monkeypatch):
    save_team_memory(empty_team_memory("t-coach", "ยอดขาย"))
    coach_payload = {
        "role_coaching": {
            "data_engineer": "ตรวจ join keys",
            "data_analyst": "นิยามยอดขายใช้ NetWR",
            "data_scientist": "เช็ค outlier",
            "business_analyst": "สรุปให้ CEO สั้นลง",
        },
        "glossary_proposals": [
            {"field_key": "CE1SATG.WW005", "definition_th": "ยอดขายตาม CO-PA"}
        ],
        "relationship_proposals": [
            {
                "from_table": "SAPHANADB.CE1SATG",
                "to_table": "SAPHANADB.KNA1",
                "join_keys": "KUNNR",
            }
        ],
    }
    fake = _FakeClient(json.dumps(coach_payload, ensure_ascii=False))
    monkeypatch.setattr(consultant_service, "_get_client", lambda: fake)

    result = await consultant_service.coach_team("t-coach", "ยอดขาย")
    assert result is not None

    mem = load_team_memory("t-coach")
    assert mem is not None
    for role in ("data_engineer", "data_analyst", "data_scientist", "business_analyst"):
        notes = mem["roles"][role]["feedback_notes"]
        assert any("[ที่ปรึกษา]" in n.get("comment", "") for n in notes)

    items = await knowledge_store.list_items("glossary", theme="ยอดขาย")
    hit = next(i for i in items if i["field_key"] == "CE1SATG.WW005")
    assert hit["status"] == "draft"
    assert hit["source"] == "consultant"
