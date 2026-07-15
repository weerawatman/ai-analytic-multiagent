import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_validation_phase1_api(client: AsyncClient, temp_storage) -> None:
    resp = await client.get("/api/v1/validation/phase1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "1"
    assert "summary" in data
    assert len(data["checks"]) >= 10
    assert data["sign_off_doc"] == "knowledge/07-testing/sign-off.md"
