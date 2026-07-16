"""Offline Fabric hardening — reachability gate, schema fallback, DA skip SQL."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.app.agents.state import AgentState
from backend.app.services import discovery_service, fabric_sql, quality_assembly
from backend.app.services.fabric_connector import FabricConnectionError


@pytest.fixture(autouse=True)
def _reset_fabric_cache():
    fabric_sql.clear_reachability_cache()
    yield
    fabric_sql.clear_reachability_cache()


def test_fabric_can_query_respects_sql_enabled(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENABLED", "false")
    monkeypatch.setenv("FABRIC_SERVER", "x.example.com")
    monkeypatch.setenv("FABRIC_DATABASE", "WH")
    monkeypatch.setenv("FABRIC_TENANT_ID", "t")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "c")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "s")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    assert fabric_sql.fabric_is_available() is True
    assert fabric_sql.fabric_can_query() is False
    get_settings.cache_clear()


def test_fabric_can_query_false_after_ping_fail_and_ttl(temp_storage, monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENABLED", "true")
    monkeypatch.setenv("FABRIC_SERVER", "x.example.com")
    monkeypatch.setenv("FABRIC_DATABASE", "WH")
    monkeypatch.setenv("FABRIC_TENANT_ID", "t")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "c")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "s")
    monkeypatch.setenv("FABRIC_REACHABILITY_TTL_SECONDS", "300")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()

    fake = MagicMock()
    fake.is_configured.return_value = True
    fake.ping.side_effect = FabricConnectionError("capacity paused", "pause")
    monkeypatch.setattr(fabric_sql, "get_fabric_connector", lambda: fake)

    assert fabric_sql.fabric_can_query() is False
    assert fake.ping.call_count == 1
    # TTL cache — second call must not ping again
    assert fabric_sql.fabric_can_query() is False
    assert fake.ping.call_count == 1
    get_settings.cache_clear()


def test_format_schema_context_pack_no_crash_when_fabric_down(temp_storage, monkeypatch):
    def boom(limit=40):
        raise FabricConnectionError("down", "ล่ม")

    monkeypatch.setattr(fabric_sql, "get_fabric_schema_text", boom)
    # Patch the import path used inside discovery_service fallback
    monkeypatch.setattr(
        "backend.app.services.fabric_sql.get_fabric_schema_text",
        boom,
    )
    text = discovery_service.format_schema_context_pack("missing-theme")
    assert "discovery" in text.lower() or "Fabric" in text or "ดิสก์" in text
    assert "Traceback" not in text


def test_format_schema_context_pack_uses_disk(temp_storage):
    theme_id = "offline-sales"
    d = temp_storage / "knowledge" / "themes" / theme_id
    d.mkdir(parents=True)
    (d / "discovery.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "table": "SAPHANADB.CE1SATG",
                        "row_count": 10,
                        "columns": [{"COLUMN_NAME": "WW005", "DATA_TYPE": "decimal"}],
                    }
                ],
                "relationships": [],
            }
        ),
        encoding="utf-8",
    )
    text = discovery_service.format_schema_context_pack(theme_id)
    assert "CE1SATG" in text
    assert "WW005" in text


def test_quality_skips_sql_when_offline(temp_storage, monkeypatch):
    monkeypatch.setattr(quality_assembly, "fabric_can_query", lambda: False)
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("should not run SQL")

    monkeypatch.setattr(quality_assembly, "run_fabric_sql", boom)
    state = AgentState(
        thread_id="t-off",
        mode="explore",
        generated_sql="SELECT 1",
        messages=[HumanMessage(content="q")],
        query_result="ANALYSIS: ok",
    )
    payload = quality_assembly.build_quality_payload(state)
    assert called["n"] == 0
    assert "offline" in payload["sample_preview"].lower() or "ข้าม" in payload["sample_preview"]
    assert payload.get("sample_data_ref") == "skipped_offline"


@pytest.mark.anyio
async def test_data_analyst_uses_discovery_and_skips_sql(temp_storage, monkeypatch):
    from backend.app.agents import data_analyst

    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: False)
    sql_calls = {"n": 0}

    async def boom_sql(*a, **k):
        sql_calls["n"] += 1
        raise AssertionError("no SQL")

    monkeypatch.setattr(data_analyst, "run_fabric_sql_async", boom_sql)

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(
                content=(
                    "ANALYSIS: draft\nSQL:\n```sql\nSELECT NETWR FROM VBRK\n```\n"
                    "ASSUMPTIONS:\n- grain daily"
                )
            )

    monkeypatch.setattr(data_analyst, "llm", FakeLLM())

    async def fake_trusted():
        return {"metrics": []}

    monkeypatch.setattr(data_analyst, "read_trusted_layer", fake_trusted)

    state = AgentState(
        thread_id="t-da",
        mode="explore",
        theme="sales",
        theme_id="sales",
        discovery_context="## SAPHANADB.VBRK\n  - NETWR (decimal)",
        messages=[HumanMessage(content="ยอดขาย")],
    )
    result = await data_analyst.data_analyst_node(state)
    assert sql_calls["n"] == 0
    assert "(Fabric not configured)" not in result["query_result"]
    assert "SQL_SKIPPED" in result["query_result"]
    assert isinstance(result["messages"][0], AIMessage)
