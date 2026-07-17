"""Phase F — Postgres numeric-column overlay (D-2 mapping → DA prompt).

Fabric reports every WH_Silver column as varchar; the Postgres mirror has a
few true numeric columns. When the DA targets the Postgres fallback it must
see which columns are truly numeric there — and the mechanism must degrade to
an empty overlay (never crash the DA path) on missing/malformed files.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from backend.app.agents import data_analyst
from backend.app.agents.state import AgentState
from backend.app.services import pg_numeric_overlay


def _write_overlay(local_dir: Path, tables: dict) -> Path:
    knowledge = local_dir / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    path = knowledge / "pg_numeric_columns.json"
    path.write_text(
        json.dumps({"version": "1.0", "tables": tables}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_load_prefers_local_file_over_template(temp_storage):
    _write_overlay(temp_storage, {"SAPHANADB.COSP_All_Cleaned": ["Total_Value"]})
    loaded = pg_numeric_overlay.load_pg_numeric_columns()
    assert loaded == {"SAPHANADB.COSP_All_Cleaned": ["Total_Value"]}


def test_load_falls_back_to_repo_template_with_verified_vbrk_seed(temp_storage):
    """No local file — the template (VBRK columns verified live in the Phase F
    deep audit) must be used so the overlay works out of the box."""
    loaded = pg_numeric_overlay.load_pg_numeric_columns()
    vbrk = loaded.get("SAPHANADB.VBRK_All_Cleaned")
    assert vbrk is not None
    assert "Net_Value_In_Document_Currency" in vbrk
    assert len(vbrk) == 6


def test_load_returns_empty_when_no_file_anywhere(temp_storage, monkeypatch):
    monkeypatch.setattr(
        pg_numeric_overlay, "_template_path", lambda: Path("nonexistent-template.json")
    )
    assert pg_numeric_overlay.load_pg_numeric_columns() == {}
    assert pg_numeric_overlay.format_pg_numeric_context() == ""


def test_load_degrades_on_malformed_local_file(temp_storage, monkeypatch):
    knowledge = temp_storage / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    (knowledge / "pg_numeric_columns.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(
        pg_numeric_overlay, "_template_path", lambda: Path("nonexistent-template.json")
    )
    # Must not raise — DA path can never break because this file is bad.
    assert pg_numeric_overlay.load_pg_numeric_columns() == {}


def test_load_skips_local_file_without_tables_mapping(temp_storage, monkeypatch):
    knowledge = temp_storage / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    (knowledge / "pg_numeric_columns.json").write_text(
        json.dumps({"version": "1.0"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        pg_numeric_overlay, "_template_path", lambda: Path("nonexistent-template.json")
    )
    assert pg_numeric_overlay.load_pg_numeric_columns() == {}


def test_format_context_lists_tables_and_cast_instruction(temp_storage):
    _write_overlay(
        temp_storage,
        {"SAPHANADB.VBRK_All_Cleaned": ["Net_Value_In_Document_Currency"]},
    )
    text = pg_numeric_overlay.format_pg_numeric_context()
    assert "SAPHANADB.VBRK_All_Cleaned" in text
    assert "Net_Value_In_Document_Currency" in text
    assert "CAST" in text  # everything else must be cast


@pytest.mark.anyio
async def test_da_prompt_includes_overlay_only_on_postgres_source(temp_storage, monkeypatch):
    """End-to-end file→prompt: when the active source is the Postgres fallback,
    the DA system prompt carries the numeric overlay; on Fabric it must not."""
    _write_overlay(
        temp_storage,
        {"SAPHANADB.VBRK_All_Cleaned": ["Net_Value_In_Document_Currency"]},
    )
    monkeypatch.setattr(data_analyst, "read_trusted_layer", AsyncMock(return_value={"metrics": []}))

    captured: dict[str, str] = {}

    class FakeLLM:
        async def ainvoke(self, messages):
            captured["system_prompt"] = messages[0]["content"]
            return SimpleNamespace(
                content="ANALYSIS: draft\nSQL:\n```sql\nSELECT 1\n```\nASSUMPTIONS:\n- none"
            )

    monkeypatch.setattr(data_analyst, "llm", FakeLLM())
    monkeypatch.setattr(
        data_analyst, "enforce_row_count_threshold_for_source_async", AsyncMock(return_value=1)
    )
    monkeypatch.setattr(
        data_analyst,
        "run_sql_async",
        AsyncMock(return_value={"rows": [{"n": 1}], "columns": ["n"], "source": "postgres"}),
    )

    state = AgentState(
        thread_id="t-overlay",
        mode="explore",
        discovery_context="## VBRK\n  - Net_Value_In_Document_Currency (varchar)",
        messages=[HumanMessage(content="ยอดขาย")],
    )

    # Postgres fallback active → overlay present.
    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: False)
    monkeypatch.setattr(data_analyst, "pg_can_query", lambda: True)
    await data_analyst.data_analyst_node(state)
    assert "PostgreSQL mirror numeric columns" in captured["system_prompt"]
    assert "SAPHANADB.VBRK_All_Cleaned" in captured["system_prompt"]

    # Fabric active → no overlay (discovery/schema pack is authoritative there).
    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: True)
    monkeypatch.setattr(
        data_analyst,
        "run_sql_async",
        AsyncMock(return_value={"rows": [{"n": 1}], "columns": ["n"], "source": "fabric"}),
    )
    await data_analyst.data_analyst_node(state)
    assert "PostgreSQL mirror numeric columns" not in captured["system_prompt"]


@pytest.mark.anyio
async def test_retry_prompt_includes_overlay_on_postgres(temp_storage, monkeypatch):
    _write_overlay(
        temp_storage,
        {"SAPHANADB.VBRK_All_Cleaned": ["Net_Value_In_Document_Currency"]},
    )
    monkeypatch.setattr(data_analyst, "fabric_can_query", lambda: False)
    monkeypatch.setattr(data_analyst, "pg_can_query", lambda: True)
    monkeypatch.setattr(data_analyst, "log_sql_failure", AsyncMock())

    captured: dict[str, str] = {}

    class FixItLLM:
        async def ainvoke(self, prompt):
            captured["retry_prompt"] = prompt
            return SimpleNamespace(content="```sql\nSELECT 1\n```")

    monkeypatch.setattr(data_analyst, "llm", FixItLLM())
    monkeypatch.setattr(
        data_analyst, "enforce_row_count_threshold_for_source_async", AsyncMock(return_value=1)
    )
    monkeypatch.setattr(
        data_analyst,
        "run_sql_async",
        AsyncMock(return_value={"rows": [{"n": 1}], "columns": ["n"], "source": "postgres"}),
    )

    state = AgentState(
        thread_id="t-overlay-retry",
        mode="explore",
        discovery_context="## VBRK",
        generated_sql="SELECT TOP 5 x FROM t",
        query_result="ANALYSIS: draft",
        sql_error="timeout: query exceeded 300s",
        sql_source="fabric",
        sql_retry_count=1,
        messages=[HumanMessage(content="ยอดขาย")],
    )
    result = await data_analyst.data_analyst_node(state)
    assert result["sql_error"] == ""
    assert "PostgreSQL mirror numeric columns" in captured["retry_prompt"]
