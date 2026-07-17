"""UI/API contract — Team Memory panel must tolerate null optional fields."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.app.services.team_memory_store import empty_team_memory, save_team_memory


def _clip(value, n: int = 19) -> str:
    """Mirrors frontend/components/team_memory_panel._clip."""
    return (value or "")[:n]


def test_clip_tolerates_none_and_missing():
    assert _clip(None) == ""
    assert _clip("") == ""
    assert _clip("2026-07-17T12:00:00+00:00") == "2026-07-17T12:00:00"
    assert _clip("short") == "short"


@pytest.mark.anyio
async def test_onboarding_api_null_onboarded_at_is_safe(client: AsyncClient, temp_storage):
    """Failed/pending onboarding stores onboarded_at=null — must not 500 the panel."""
    save_team_memory(
        {
            **empty_team_memory("cb7039df", "Saphanadb"),
            "status": "failed",
            "onboarded_at": None,
            "team_summary": "",
            "recommended_tables": [],
            "key_metrics": [],
        }
    )

    response = await client.get("/api/v1/onboarding/cb7039df")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["onboarded_at"] is None
    # Panel caption must not crash on None (contract for Streamlit [:19] callers).
    assert _clip(data.get("onboarded_at")) == ""
    assert isinstance(data.get("roles"), dict)
    for role in ("data_engineer", "data_scientist", "data_analyst", "business_analyst"):
        assert role in data["roles"]
