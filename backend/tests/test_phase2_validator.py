"""Tests for Phase 2 validator."""

import pytest

from backend.app.services.phase2_validator import run_phase2_validation


@pytest.mark.anyio
async def test_phase2_validation_core_checks_pass(temp_storage):
    result = await run_phase2_validation()
    assert result["phase"] == "2"
    assert result["summary"]["total"] >= 7

    check_ids = {c["id"] for c in result["checks"]}
    assert "P2-1-discovery" in check_ids
    assert "P2-2-skills" in check_ids
    assert "P2-5-graph" in check_ids

    core = [c for c in result["checks"] if c["id"] in ("P2-1-discovery", "P2-2-skills", "P2-4-ba", "P2-5-graph")]
    assert all(c["passed"] for c in core)


@pytest.mark.anyio
async def test_phase2_validation_api(client):
    response = await client.get("/api/v1/validation/phase2")
    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "2"
    assert "checks" in data
