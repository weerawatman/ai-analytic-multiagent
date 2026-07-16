"""API/UI contract tests for consultant notes in Team Memory."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.app.services.team_memory_store import (
    append_consultant_note,
    empty_team_memory,
    save_team_memory,
)


@pytest.mark.anyio
async def test_onboarding_api_returns_consultant_notes(client: AsyncClient, temp_storage):
    save_team_memory(empty_team_memory("theme-notes", "ยอดขาย"))
    append_consultant_note("theme-notes", "คำแนะนำทดสอบจากที่ปรึกษา")

    response = await client.get("/api/v1/onboarding/theme-notes")
    assert response.status_code == 200
    data = response.json()
    assert "consultant_notes" in data
    assert len(data["consultant_notes"]) == 1
    assert "ที่ปรึกษา" in data["consultant_notes"][0]["note"]


@pytest.mark.anyio
async def test_consultant_status_disabled_when_flag_off(client: AsyncClient, monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENABLED", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    response = await client.get("/api/v1/consultant/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    get_settings.cache_clear()
