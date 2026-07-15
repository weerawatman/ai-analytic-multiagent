import pytest

from backend.app.core.config import get_settings
from backend.app.services import backlog_store, chat_store
from backend.app.services.local_paths import ensure_local_structure


@pytest.fixture
def temp_storage(tmp_path, monkeypatch):
    local = tmp_path / "local"
    monkeypatch.setenv("DATA_LOCAL_DIR", str(local))
    get_settings.cache_clear()
    ensure_local_structure()
    chat_store.init_chat_db()
    yield local
    get_settings.cache_clear()


def test_chat_store_persists_messages(temp_storage) -> None:
    chat_store.add_message("thread-1", role="user", content="สวัสดี")
    chat_store.add_message(
        "thread-1", role="assistant", content="Hello", agent="data_analyst"
    )

    messages = chat_store.get_messages("thread-1")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["agent"] == "data_analyst"

    sessions = chat_store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 2


def test_backlog_create_and_update(temp_storage) -> None:
    item = backlog_store.create_item(
        {
            "theme": "sales",
            "question_th": "ยอดขายเป็นอย่างไร?",
            "answer_summary_th": "draft",
            "sql_primary": "SELECT 1",
        }
    )
    assert item["status"] == "new"
    assert item["id"]

    updated = backlog_store.update_item(
        item["id"],
        {"status": "discussing", "feedback": "รอ confirm กับ BA"},
    )
    assert updated["status"] == "discussing"
    assert len(updated["ba_da_feedback"]) == 1


def test_backlog_list_filter(temp_storage) -> None:
    backlog_store.create_item({"theme": "sales", "question_th": "Q1", "status": "new"})
    backlog_store.create_item({"theme": "inventory", "question_th": "Q2", "status": "validated"})

    assert len(backlog_store.list_items(status="new")) == 1
    assert len(backlog_store.list_items(theme="inventory")) == 1


@pytest.mark.anyio
async def test_semantic_trusted_and_draft(temp_storage) -> None:
    from backend.app.services.semantic_store import (
        promote_metric,
        read_draft_layer,
        read_trusted_layer,
        write_semantic_layer,
    )

    await write_semantic_layer({"version": "1.0", "metrics": [{"metric_key": "draft_m"}]})
    draft = await read_draft_layer()
    assert draft["metrics"][0]["metric_key"] == "draft_m"

    await promote_metric(
        {
            "metric_key": "revenue",
            "display_name_th": "รายได้",
            "business_definition_th": "นิยาม",
        }
    )
    trusted = await read_trusted_layer()
    assert any(m["metric_key"] == "revenue" for m in trusted["metrics"])
