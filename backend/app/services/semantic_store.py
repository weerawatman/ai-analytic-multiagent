import json
import asyncio
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger

SEMANTIC_LAYER_PATH = Path("/app/data/semantic_layer.json")

_lock = asyncio.Lock()


async def read_semantic_layer() -> dict[str, Any]:
    """Read the semantic layer JSON file safely."""
    async with _lock:
        try:
            if not SEMANTIC_LAYER_PATH.exists():
                logger.warning("semantic_layer.json not found, returning empty dict")
                return {}
            text = await asyncio.to_thread(SEMANTIC_LAYER_PATH.read_text, "utf-8")
            data: dict[str, Any] = json.loads(text)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read semantic layer: %s", e)
            return {}


async def write_semantic_layer(data: dict[str, Any]) -> None:
    """Write to the semantic layer JSON file safely with atomic write."""
    async with _lock:
        try:
            tmp_path = SEMANTIC_LAYER_PATH.with_suffix(".tmp")
            content = json.dumps(data, indent=2, ensure_ascii=False)
            await asyncio.to_thread(tmp_path.write_text, content, "utf-8")
            await asyncio.to_thread(tmp_path.replace, SEMANTIC_LAYER_PATH)
            logger.info("Semantic layer updated successfully")
        except OSError as e:
            logger.error("Failed to write semantic layer: %s", e)
            raise
