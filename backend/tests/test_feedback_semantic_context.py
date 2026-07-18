"""Phase J feedback-context wiring — semantic path vs chronological fallback."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.app.agents.context_nodes import _feedback_context_for
from backend.app.services import feedback_store


def test_format_feedback_entries_shared_shape():
    entries = [
        {"action": "approve", "role": "DA", "comment": "ok"},
        {"action": "revise", "role": "BA", "comment": "fix filter"},
    ]
    text = feedback_store.format_feedback_entries(entries)
    assert "CEO Feedback" in text
    assert "[approve] DA: ok" in text
    assert "[revise] BA: fix filter" in text


def test_feedback_context_uses_chronological_when_embedding_disabled(monkeypatch, temp_storage):
    theme_id = "theme-fb"
    for i in range(12):
        feedback_store.add_feedback(
            theme_id,
            brief_id=f"b{i}",
            role="DA",
            action="note",
            comment=f"entry-{i:02d}",
        )
    settings = SimpleNamespace(embedding_context_enabled=False)
    state = MagicMock()
    state.messages = []
    text = _feedback_context_for(theme_id, state, settings)
    # Default path keeps last 10 of 12
    assert "entry-11" in text
    assert "entry-02" in text
    assert "entry-00" not in text
    assert "entry-01" not in text


def test_feedback_context_semantic_path_selects_relevant(monkeypatch, temp_storage):
    theme_id = "theme-sem"
    for i in range(8):
        feedback_store.add_feedback(
            theme_id,
            brief_id=f"b{i}",
            role="DA",
            action="note",
            comment=f"generic note {i}",
        )
    feedback_store.add_feedback(
        theme_id,
        brief_id="special",
        role="DA",
        action="revise",
        comment="always use NetValue not Gross",
    )

    async def _fake_select(query, candidates, **kwargs):
        return [c for c in candidates if "NetValue" in (c.get("comment") or "")]

    monkeypatch.setattr(
        "backend.app.services.embedding_service.select_relevant", _fake_select
    )

    settings = SimpleNamespace(embedding_context_enabled=True)
    human = MagicMock()
    human.type = "human"
    human.content = "how should we measure revenue?"
    state = MagicMock()
    state.messages = [human]

    text = _feedback_context_for(theme_id, state, settings)
    assert "NetValue" in text
    assert "generic note 0" not in text
