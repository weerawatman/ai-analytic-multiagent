import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_promotion_preview_api(client: AsyncClient, temp_storage) -> None:
    create = await client.post(
        "/api/v1/backlog/",
        json={
            "theme": "sales",
            "question_th": "promote me?",
            "answer_summary_th": "summary",
            "sql_primary": "SELECT 1",
            "status": "validated",
        },
    )
    item_id = create.json()["id"]

    preview = await client.get(f"/api/v1/semantic/promote/{item_id}/preview")
    assert preview.status_code == 200
    data = preview.json()
    assert data["metric"]["source_backlog_id"] == item_id
    assert "promote me" in data["preview_markdown"]


@pytest.mark.anyio
async def test_promotion_approve_api(client: AsyncClient, temp_storage) -> None:
    create = await client.post(
        "/api/v1/backlog/",
        json={
            "theme": "sales",
            "question_th": "approve test",
            "sql_primary": "SELECT 2",
            "status": "validated",
        },
    )
    item_id = create.json()["id"]

    approve = await client.post(
        f"/api/v1/semantic/promote/{item_id}/approve",
        json={"approved": True, "approved_by": "test_user"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "promoted"

    trusted = await client.get("/api/v1/semantic/trusted")
    assert any(m.get("source_backlog_id") == item_id for m in trusted.json()["metrics"])


@pytest.mark.anyio
async def test_promotion_preview_rejects_new_status(client: AsyncClient, temp_storage) -> None:
    create = await client.post(
        "/api/v1/backlog/",
        json={"theme": "sales", "question_th": "too early", "status": "new"},
    )
    item_id = create.json()["id"]
    resp = await client.get(f"/api/v1/semantic/promote/{item_id}/preview")
    assert resp.status_code == 400
