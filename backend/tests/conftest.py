import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def temp_storage(tmp_path, monkeypatch):
    local = tmp_path / "local"
    monkeypatch.setenv("DATA_LOCAL_DIR", str(local))
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    from backend.app.services.local_paths import ensure_local_structure
    from backend.app.services.chat_store import init_chat_db

    ensure_local_structure()
    init_chat_db()
    yield local
    get_settings.cache_clear()


@pytest.fixture
def consultant_enabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("CONSULTANT_ENABLED", "true")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
