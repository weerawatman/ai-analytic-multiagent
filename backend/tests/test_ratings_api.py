"""Phase G1b — answer ratings API."""

from __future__ import annotations

import pytest

from backend.app.services import chat_store
from backend.app.services.job_store import init_jobs_db


@pytest.fixture
def ratings_db(temp_storage):
    init_jobs_db()
    return temp_storage


@pytest.mark.asyncio
async def test_create_and_list_ratings(client, ratings_db):
    chat_store.ensure_session("sess-rate")
    resp = await client.post(
        "/api/v1/chat/rating",
        json={
            "session_id": "sess-rate",
            "rating": "up",
            "comment": "ดี",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["rating"] == "up"
    assert body["session_id"] == "sess-rate"

    listed = await client.get("/api/v1/chat/ratings", params={"session_id": "sess-rate"})
    assert listed.status_code == 200
    data = listed.json()
    assert data["total"] >= 1
    assert any(i["id"] == body["id"] for i in data["items"])


@pytest.mark.asyncio
async def test_rating_rejects_invalid(client, ratings_db):
    resp = await client.post(
        "/api/v1/chat/rating",
        json={"session_id": "s", "rating": "maybe"},
    )
    assert resp.status_code == 400


def test_reason_tag_validation(ratings_db):
    with pytest.raises(ValueError):
        chat_store.add_answer_rating("s", rating="down", reason_tag="nope")
    row = chat_store.add_answer_rating(
        "s2", rating="down", reason_tag="wrong_number", corrected_answer="42"
    )
    assert row["reason_tag"] == "wrong_number"
    assert row["corrected_answer"] == "42"
