import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_backlog_api_crud(client: AsyncClient, temp_storage) -> None:
    create_resp = await client.post(
        "/api/v1/backlog/",
        json={
            "theme": "sales",
            "question_th": "ยอดขายเดือนนี้?",
            "answer_summary_th": "สรุป draft",
            "sql_primary": "SELECT 1",
        },
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/backlog/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    patch_resp = await client.patch(
        f"/api/v1/backlog/{item_id}",
        json={"status": "validated", "feedback": "BA confirm แล้ว"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "validated"


@pytest.mark.anyio
async def test_semantic_trusted_endpoint(client: AsyncClient, temp_storage) -> None:
    resp = await client.get("/api/v1/semantic/trusted")
    assert resp.status_code == 200
    assert "metrics" in resp.json()


@pytest.mark.anyio
async def test_themes_list_empty(client: AsyncClient, temp_storage) -> None:
    resp = await client.get("/api/v1/themes/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["themes"] == []
