"""Run team onboarding pipeline for a theme."""

from __future__ import annotations

from typing import Any

from backend.app.agents.onboarding_graph import build_onboarding_input, onboarding_graph
from backend.app.core.logger import logger
from backend.app.services.discovery_service import load_discovery
from backend.app.services.team_memory_store import load_team_memory


async def run_onboarding(theme_id: str, theme_name: str = "") -> dict[str, Any]:
    discovery = load_discovery(theme_id)
    if not discovery:
        raise ValueError(f"No discovery for theme {theme_id} — run discovery first")

    logger.info("Starting team onboarding theme=%s", theme_id)
    input_state = build_onboarding_input(theme_id, theme_name)

    try:
        result = await onboarding_graph.ainvoke(input_state)
    except Exception as exc:
        logger.error("Onboarding failed theme=%s: %s", theme_id, exc)
        memory = load_team_memory(theme_id)
        if memory:
            memory["status"] = "failed"
            from backend.app.services.team_memory_store import save_team_memory

            save_team_memory(memory)
        raise

    memory = load_team_memory(theme_id)
    logger.info("Team onboarding completed theme=%s status=%s", theme_id, memory.get("status") if memory else "?")
    return {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "status": memory.get("status", "completed") if memory else "completed",
        "team_summary": memory.get("team_summary", "") if memory else result.get("team_summary", ""),
        "recommended_tables": memory.get("recommended_tables", []) if memory else [],
        "key_metrics": memory.get("key_metrics", []) if memory else [],
        "roles": memory.get("roles", {}) if memory else {},
    }
