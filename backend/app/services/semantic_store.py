import json
import asyncio
from pathlib import Path
from typing import Any

from backend.app.core.logger import logger
from backend.app.services.local_paths import ensure_local_structure, get_local_dir, get_project_root

_lock = asyncio.Lock()


def _trusted_path() -> Path:
    ensure_local_structure()
    return get_local_dir() / "semantic" / "trusted.json"


def _draft_path() -> Path:
    ensure_local_structure()
    return get_local_dir() / "semantic" / "draft.json"


def _legacy_path() -> Path:
    return get_project_root() / "data" / "semantic_layer.json"


def _empty_layer() -> dict[str, Any]:
    return {"version": "1.0", "metrics": []}


async def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_layer()
    text = await asyncio.to_thread(path.read_text, "utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


async def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    content = json.dumps(data, indent=2, ensure_ascii=False)
    await asyncio.to_thread(tmp_path.write_text, content, "utf-8")
    await asyncio.to_thread(tmp_path.replace, path)


async def read_semantic_layer() -> dict[str, Any]:
    """Read trusted semantic layer (backward-compatible name)."""
    async with _lock:
        try:
            trusted = await _read_json(_trusted_path())
            if trusted.get("metrics"):
                return trusted

            legacy = _legacy_path()
            if legacy.exists():
                logger.info("Loading legacy semantic_layer.json as fallback")
                return await _read_json(legacy)

            return trusted
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read semantic layer: %s", e)
            return _empty_layer()


async def read_trusted_layer() -> dict[str, Any]:
    async with _lock:
        try:
            return await _read_json(_trusted_path())
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read trusted layer: %s", e)
            return _empty_layer()


async def read_draft_layer() -> dict[str, Any]:
    async with _lock:
        try:
            return await _read_json(_draft_path())
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read draft layer: %s", e)
            return _empty_layer()


async def write_semantic_layer(data: dict[str, Any]) -> None:
    """Write draft semantic proposals (backward-compatible name)."""
    async with _lock:
        try:
            await _write_json(_draft_path(), data)
            logger.info("Semantic draft layer updated")
        except OSError as e:
            logger.error("Failed to write semantic draft layer: %s", e)
            raise


async def write_trusted_layer(data: dict[str, Any]) -> None:
    async with _lock:
        try:
            await _write_json(_trusted_path(), data)
            logger.info("Trusted semantic layer updated")
        except OSError as e:
            logger.error("Failed to write trusted layer: %s", e)
            raise


async def promote_metric(metric: dict[str, Any]) -> dict[str, Any]:
    """Append a validated metric to trusted layer."""
    async with _lock:
        trusted = await _read_json(_trusted_path())
        metrics: list[dict[str, Any]] = trusted.setdefault("metrics", [])

        metric_key = metric.get("metric_key")
        metrics = [m for m in metrics if m.get("metric_key") != metric_key]
        metrics.append(metric)
        trusted["metrics"] = metrics

        await _write_json(_trusted_path(), trusted)
        return metric
