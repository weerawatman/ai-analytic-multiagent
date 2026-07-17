"""Onboarding graph — state merge + DE→DS→DA→BA order for Postgres-scan themes."""

from __future__ import annotations

import json

import pytest

from backend.app.agents.onboarding_graph import (
    OnboardingState,
    build_onboarding_graph,
    build_onboarding_input,
)
from backend.app.agents import onboarding_nodes
from backend.app.services.team_memory_store import load_team_memory
from backend.app.services.theme_service import save_cached_themes


@pytest.fixture
def postgres_scan_theme(temp_storage):
    """Theme record shaped like Postgres-mirror scan output (optional fields sparse)."""
    theme_id = "cb7039df"
    save_cached_themes(
        {
            "scanned_at": "2026-07-17T12:00:00+00:00",
            "database": "WH_Silver",
            "total_tables_scanned": 8,
            "source": "postgres",
            "message": "Fabric ไม่พร้อม — สแกนจาก Postgres mirror (WH_Silver) แทน",
            "themes": [
                {
                    "id": theme_id,
                    "name_th": "Saphanadb",
                    # Postgres-scan heuristics may omit some Fabric-era fields.
                    "rationale_th": None,
                    "table_count": 8,
                    "sample_tables": [
                        "SAPHANADB.VBRK_All_Cleaned",
                        "SAPHANADB.Dim_KNA1_Cleaned",
                    ],
                    "starter_questions_th": ["ยอดขายแนวโน้มอย่างไร?"],
                }
            ],
        }
    )
    discovery_dir = temp_storage / "knowledge" / "themes" / theme_id
    discovery_dir.mkdir(parents=True, exist_ok=True)
    (discovery_dir / "discovery.json").write_text(
        json.dumps(
            {
                "theme_id": theme_id,
                "discovered_at": "2026-07-17T12:01:00+00:00",
                "database": "WH_Silver",
                "tables_profiled": 2,
                "profiles": [
                    {
                        "table": "SAPHANADB.VBRK_All_Cleaned",
                        "row_count": 1000,
                        "columns": [
                            {"COLUMN_NAME": "Billing_Document", "DATA_TYPE": "varchar"},
                            {"COLUMN_NAME": "Net_Value", "DATA_TYPE": "varchar"},
                        ],
                    }
                ],
                "relationships": [],
                "source": "postgres",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return theme_id


@pytest.mark.anyio
async def test_onboarding_preserves_theme_id_across_nodes(postgres_scan_theme, monkeypatch):
    """Regression: StateGraph(dict) used to replace state and drop theme_id after DE."""
    theme_id = postgres_scan_theme
    calls: list[str] = []

    async def fake_invoke(role, system, user_task):
        calls.append(role)
        return (
            f"HANDOFF: สรุป {role} สำหรับ Saphanadb\n"
            '{"primary_tables":["SAPHANADB.VBRK_All_Cleaned"],'
            '"metric_candidates":[{"name_th":"ยอดขาย"}],'
            '"metric_definitions":[{"name_th":"ยอดขาย","definition_th":"SUM Net_Value","status":"draft"}],'
            '"hypotheses":["ยอดขายเติบโต"],"sanity_checks":["เทียบรายเดือน"],'
            '"recommended_primary_table":"SAPHANADB.VBRK_All_Cleaned"}'
        )

    monkeypatch.setattr(onboarding_nodes, "_invoke_role", fake_invoke)

    graph = build_onboarding_graph().compile()
    input_state = build_onboarding_input(theme_id, "Saphanadb")
    assert input_state["theme_id"] == theme_id

    result = await graph.ainvoke(input_state)
    # Typed OnboardingState merges — theme_id must survive every node.
    assert result["theme_id"] == theme_id
    assert result["status"] == "completed"
    assert calls == ["data_engineer", "data_scientist", "data_analyst", "business_analyst"]

    memory = load_team_memory(theme_id)
    assert memory is not None
    assert memory["status"] == "completed"
    assert memory["theme_name"] == "Saphanadb"
    assert memory["roles"]["data_engineer"]["status"] == "completed"
    assert memory["roles"]["data_scientist"]["status"] == "completed"
    assert memory["roles"]["data_analyst"]["status"] == "completed"
    assert memory["roles"]["business_analyst"]["status"] == "completed"
    assert memory["onboarded_at"]  # set on finalize


@pytest.mark.anyio
async def test_onboarding_de_update_does_not_wipe_theme_id(postgres_scan_theme, monkeypatch):
    theme_id = postgres_scan_theme

    async def fake_invoke(role, system, user_task):
        return 'HANDOFF: DE only\n{"primary_tables":["SAPHANADB.VBRK_All_Cleaned"]}'

    monkeypatch.setattr(onboarding_nodes, "_invoke_role", fake_invoke)

    state = OnboardingState(
        theme_id=theme_id,
        theme="Saphanadb",
        discovery_context="## SAPHANADB.VBRK_All_Cleaned\n  - Net_Value",
    )
    out = await onboarding_nodes.onboarding_de_node(state)
    assert "theme_id" not in out  # partial update — must not need to re-emit
    merged = state.model_copy(update=out)
    assert merged.theme_id == theme_id
    assert merged.schema_info
    out_ds = await onboarding_nodes.onboarding_ds_node(merged)
    merged2 = merged.model_copy(update=out_ds)
    assert merged2.theme_id == theme_id
    assert merged2.analysis_summary


def test_onboarding_graph_edge_order():
    """Compiled graph edges: DE → DS → DA → BA → finalize."""
    graph = build_onboarding_graph().compile()
    g = graph.get_graph()
    edges = {(e.source, e.target) for e in g.edges}
    assert ("de_onboard", "ds_onboard") in edges
    assert ("ds_onboard", "da_onboard") in edges
    assert ("da_onboard", "ba_onboard") in edges
    assert ("ba_onboard", "finalize") in edges
    # Old DA-before-DS edge must be gone
    assert ("de_onboard", "da_onboard") not in edges
    assert ("da_onboard", "ds_onboard") not in edges
