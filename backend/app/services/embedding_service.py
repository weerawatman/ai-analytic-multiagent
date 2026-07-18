"""Embedding service (Phase J) — Ollama `nomic-embed-text` + numpy cosine on
a SQLite BLOB cache in `analytics.db`. No vector DB (roadmap §3 locked
decision — INV-1 already forbids one).

Every public function here degrades to a safe fallback instead of raising —
callers (context_nodes.py, sql_pattern_store.py) can wire this in without
their own try/except, and a down/unpulled Ollama embedding model never
breaks a chat turn, it just falls back to today's truncation behavior.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from backend.app.core.llm import make_embed_ollama
from backend.app.core.logger import logger
from backend.app.services.snapshot_store import get_analytics_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings_cache (
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    model TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (namespace, source_id, model)
);
"""


def init_embedding_tables(db_path: Path | None = None) -> None:
    with get_analytics_connection(db_path) as conn:
        conn.executescript(_SCHEMA)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _vector_to_blob(vec: list[float]) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _blob_to_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def _default_model() -> str:
    from backend.app.core.config import get_settings

    return get_settings().ollama_embed_model


async def embed_text(text: str, *, model: str | None = None) -> list[float] | None:
    """Embed one string via Ollama. Returns None on any failure (never raises)."""
    try:
        client = make_embed_ollama(model=model)
        return await client.aembed_query(text)
    except Exception as exc:
        logger.warning("Embedding call failed (text len=%d): %s", len(text or ""), exc)
        return None


async def get_or_compute_embedding(
    namespace: str,
    source_id: str,
    text: str,
    *,
    model: str | None = None,
    db_path: Any = None,
) -> np.ndarray | None:
    """Cached embedding lookup — recomputes only when the source text changed."""
    resolved_model = model or _default_model()
    h = _text_hash(text)
    with get_analytics_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT text_hash, vector FROM embeddings_cache
            WHERE namespace = ? AND source_id = ? AND model = ?
            """,
            (namespace, source_id, resolved_model),
        ).fetchone()
    if row is not None and row["text_hash"] == h:
        return _blob_to_vector(row["vector"])

    vec = await embed_text(text, model=resolved_model)
    if vec is None:
        return None
    with get_analytics_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO embeddings_cache
                (namespace, source_id, model, text_hash, dim, vector, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, source_id, model) DO UPDATE SET
                text_hash = excluded.text_hash,
                dim = excluded.dim,
                vector = excluded.vector,
                created_at = excluded.created_at
            """,
            (
                namespace,
                source_id,
                resolved_model,
                h,
                len(vec),
                _vector_to_blob(vec),
                _utc_now(),
            ),
        )
    return np.asarray(vec, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-12:
        return 0.0
    return float(np.dot(a, b) / denom)


async def select_relevant(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    k: int,
    namespace: str,
    id_key: str = "id",
    text_key: str = "text",
    model: str | None = None,
    db_path: Any = None,
) -> list[dict[str, Any]]:
    """Rank ``candidates`` by semantic similarity to ``query``.

    Hard-falls-back to ``candidates[:k]`` (today's truncation order) on ANY
    embedding error — a down/unpulled Ollama embedding model must never break
    the caller, only degrade it to its pre-Phase-J behavior.
    """
    if not candidates:
        return []
    if k >= len(candidates):
        return list(candidates)
    try:
        query_vec = await embed_text(query, model=model)
        if query_vec is None:
            raise RuntimeError("query embedding unavailable")
        query_arr = np.asarray(query_vec, dtype=np.float32)

        scored: list[tuple[float, dict[str, Any]]] = []
        for c in candidates:
            cid = str(c.get(id_key))
            text = str(c.get(text_key) or "")
            if not text.strip():
                continue
            vec = await get_or_compute_embedding(
                namespace, cid, text, model=model, db_path=db_path
            )
            if vec is None:
                raise RuntimeError(f"candidate embedding unavailable for {cid}")
            scored.append((cosine_similarity(query_arr, vec), c))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [c for _, c in scored[:k]]
    except Exception as exc:
        logger.warning(
            "select_relevant fell back to truncation (namespace=%s, k=%d): %s",
            namespace,
            k,
            exc,
        )
        return list(candidates[:k])
