"""Tests for team memory store and feedback router."""

import asyncio

from backend.app.services import feedback_router, team_memory_store


def test_team_memory_lifecycle(temp_storage):
    team_memory_store.update_role_artifact(
        "sales",
        "data_engineer",
        handoff_summary="โครงสร้าง VBRK และ KNA1",
        artifact={"primary_tables": ["SAPHANADB.VBRK_All_Cleaned"]},
        theme_name="ยอดขาย",
    )
    team_memory_store.finalize_team_memory(
        "sales",
        team_summary="สรุปทีม",
        recommended_tables=["SAPHANADB.VBRK_All_Cleaned"],
        key_metrics=["ยอดขายรายเดือน"],
    )
    data = team_memory_store.load_team_memory("sales")
    assert data is not None
    assert data["status"] == "completed"
    assert "VBRK" in data["roles"]["data_engineer"]["handoff_summary"]

    ctx = team_memory_store.format_team_memory_context("sales")
    assert "Team Memory" in ctx
    assert "ยอดขายรายเดือน" in ctx


def test_prior_handoffs(temp_storage):
    team_memory_store.update_role_artifact(
        "t1",
        "data_engineer",
        handoff_summary="DE handoff",
        artifact={},
    )
    team_memory_store.update_role_artifact(
        "t1",
        "data_analyst",
        handoff_summary="DA handoff",
        artifact={},
    )
    prior = team_memory_store.get_prior_handoffs("t1", "data_scientist")
    assert "DE handoff" in prior
    assert "DA handoff" in prior


def test_feedback_router_da_glossary(temp_storage):
    async def run():
        result = await feedback_router.apply_feedback(
            "sales",
            role="data_analyst",
            action="approve",
            comment="ยอดขาย = SUM(Net_Value_In_Document_Currency) จาก CE1SATG",
            theme_name="ยอดขาย",
        )
        return result

    result = asyncio.run(run())
    assert "glossary" in str(result.get("applied", []))


def test_feedback_router_de_relationship(temp_storage):
    async def run():
        return await feedback_router.apply_feedback(
            "sales",
            role="data_engineer",
            action="approve",
            comment="SAPHANADB.VBRK_All_Cleaned join SAPHANADB.Dim_KNA1_Cleaned on Sold_To_Party = KUNNR",
            theme_name="ยอดขาย",
        )

    result = asyncio.run(run())
    assert result.get("applied")
