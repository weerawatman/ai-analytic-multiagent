"""Load agent SKILL.md files into system prompts."""

from pathlib import Path

_SKILLS_ROOT = Path(__file__).resolve().parent / "skills"


def load_agent_skill(agent_name: str) -> str:
    """Return skill text for agent, or empty string if missing."""
    path = _SKILLS_ROOT / agent_name / "SKILL.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
