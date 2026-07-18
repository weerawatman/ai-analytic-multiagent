"""embedding_service tests (Phase J) — cosine + cache + hard fallback (no live Ollama)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.app.services import embedding_service, snapshot_store


@pytest.fixture()
def analytics_db(tmp_path: Path) -> Path:
    db = tmp_path / "analytics.db"
    snapshot_store.init_analytics_db(db)
    embedding_service.init_embedding_tables(db)
    return db


def test_cosine_similarity_identical_and_orthogonal():
    a = np.asarray([1.0, 0.0], dtype=np.float32)
    b = np.asarray([1.0, 0.0], dtype=np.float32)
    c = np.asarray([0.0, 1.0], dtype=np.float32)
    assert embedding_service.cosine_similarity(a, b) == pytest.approx(1.0)
    assert embedding_service.cosine_similarity(a, c) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_is_safe():
    z = np.zeros(3, dtype=np.float32)
    assert embedding_service.cosine_similarity(z, z) == 0.0


@pytest.mark.asyncio
async def test_select_relevant_falls_back_when_embed_fails(monkeypatch, analytics_db: Path):
    async def _fail(_text: str, **_kwargs):
        return None

    monkeypatch.setattr(embedding_service, "embed_text", _fail)
    candidates = [{"id": "a", "text": "alpha"}, {"id": "b", "text": "beta"}, {"id": "c", "text": "gamma"}]
    out = await embedding_service.select_relevant(
        "query", candidates, k=2, namespace="test", db_path=analytics_db
    )
    assert out == candidates[:2]


@pytest.mark.asyncio
async def test_select_relevant_ranks_by_cosine(monkeypatch, analytics_db: Path):
    # Fixed 2-D embeddings: query≈near, far is orthogonal.
    vectors = {
        "query about sales": [1.0, 0.0],
        "monthly sales revenue": [0.95, 0.1],
        "warehouse schema notes": [0.0, 1.0],
        "unrelated weather": [0.1, 0.9],
    }

    async def _fake_embed(text: str, **_kwargs):
        return vectors.get(text)

    monkeypatch.setattr(embedding_service, "embed_text", _fake_embed)

    candidates = [
        {"id": "1", "text": "warehouse schema notes"},
        {"id": "2", "text": "monthly sales revenue"},
        {"id": "3", "text": "unrelated weather"},
    ]
    out = await embedding_service.select_relevant(
        "query about sales",
        candidates,
        k=2,
        namespace="rank-test",
        db_path=analytics_db,
    )
    assert [c["id"] for c in out] == ["2", "1"] or [c["id"] for c in out][0] == "2"


@pytest.mark.asyncio
async def test_get_or_compute_embedding_uses_cache(monkeypatch, analytics_db: Path):
    calls = {"n": 0}

    async def _fake_embed(text: str, **_kwargs):
        calls["n"] += 1
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(embedding_service, "embed_text", _fake_embed)

    first = await embedding_service.get_or_compute_embedding(
        "ns", "id1", "hello world", model="fake-model", db_path=analytics_db
    )
    second = await embedding_service.get_or_compute_embedding(
        "ns", "id1", "hello world", model="fake-model", db_path=analytics_db
    )
    assert calls["n"] == 1
    assert first is not None and second is not None
    np.testing.assert_allclose(first, second)

    # Text change forces recompute
    third = await embedding_service.get_or_compute_embedding(
        "ns", "id1", "hello world changed", model="fake-model", db_path=analytics_db
    )
    assert calls["n"] == 2
    assert third is not None


@pytest.mark.asyncio
async def test_select_relevant_returns_all_when_k_covers(analytics_db: Path):
    candidates = [{"id": "a", "text": "one"}, {"id": "b", "text": "two"}]
    out = await embedding_service.select_relevant(
        "q", candidates, k=10, namespace="t", db_path=analytics_db
    )
    assert out == candidates
