"""In-flight chat lock — one request per thread at a time."""

from __future__ import annotations

import asyncio

_locks: dict[str, asyncio.Lock] = {}


def thread_lock(thread_id: str) -> asyncio.Lock:
    if thread_id not in _locks:
        _locks[thread_id] = asyncio.Lock()
    return _locks[thread_id]
