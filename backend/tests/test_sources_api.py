"""Phase F — /api/v1/fabric/sources: active source + per-source status.

The UI reads this endpoint to tell the CEO which database will answer the
next question (Fabric primary / Postgres fallback / offline). It must reflect
the same decision the dispatch path makes, and must never leak secrets.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from backend.app.api.routes import fabric as fabric_route


@pytest.mark.anyio
async def test_sources_fabric_active(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(fabric_route, "fabric_can_query", lambda: True)
    monkeypatch.setattr(fabric_route, "pg_can_query", lambda: True)

    response = await client.get("/api/v1/fabric/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["active_source"] == "fabric"
    assert data["fabric"]["reachable"] is True
    assert "detail_th" in data and data["detail_th"]


@pytest.mark.anyio
async def test_sources_postgres_fallback_active(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(fabric_route, "fabric_can_query", lambda: False)
    monkeypatch.setattr(fabric_route, "pg_can_query", lambda: True)

    response = await client.get("/api/v1/fabric/sources")
    data = response.json()
    assert data["active_source"] == "postgres"
    assert data["postgres_replica"]["reachable"] is True
    # Thai message must make the fallback (and freshness caveat) explicit.
    assert "สำรอง" in data["detail_th"]


@pytest.mark.anyio
async def test_sources_offline_when_both_down(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(fabric_route, "fabric_can_query", lambda: False)
    monkeypatch.setattr(fabric_route, "pg_can_query", lambda: False)

    response = await client.get("/api/v1/fabric/sources")
    data = response.json()
    assert data["active_source"] == "offline"
    assert "Offline" in data["detail_th"]


@pytest.mark.anyio
async def test_sources_response_never_contains_secrets(client: AsyncClient, monkeypatch) -> None:
    """Database names are fine; hosts, users, passwords, tenant/client IDs are not."""
    monkeypatch.setattr(fabric_route, "fabric_can_query", lambda: False)
    monkeypatch.setattr(fabric_route, "pg_can_query", lambda: True)

    response = await client.get("/api/v1/fabric/sources")
    body = json.dumps(response.json()).lower()
    for banned in ("password", "secret", "client_id", "tenant", "user", "host", "server"):
        assert banned not in body, f"sources endpoint leaked field: {banned}"
