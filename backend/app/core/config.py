from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL (legacy — not used in Phase 1 runtime path)
    postgres_user: str = "analytics_user"
    postgres_password: str = "analytics_secret_2024"
    postgres_db: str = "analytics_db"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    # Microsoft Fabric Data Warehouse
    fabric_server: str = ""
    fabric_database: str = ""
    fabric_tenant_id: str = ""
    fabric_client_id: str = ""
    fabric_client_secret: str = ""
    fabric_odbc_driver: str = "ODBC Driver 18 for SQL Server"
    fabric_connection_timeout: int = 30
    fabric_query_timeout: int = 300
    fabric_max_rows: int = 100
    # Pre-flight COUNT(*) threshold — reject oversized result sets before fetch (Phase D)
    fabric_row_count_threshold: int = 50000
    # When false, skip all live SQL even if credentials are present (Fabric pause / offline Explore)
    fabric_sql_enabled: bool = True
    # Seconds to remember a failed ping before retrying (avoid long timeouts on every query)
    fabric_reachability_ttl_seconds: int = 300

    # Ollama (native Windows defaults)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:14b"
    ollama_model_analyst: str = ""
    ollama_model_ba: str = ""
    ollama_num_ctx: int = 16384
    ollama_num_predict: int | None = None

    # FastAPI
    fastapi_host: str = "127.0.0.1"
    fastapi_port: int = 8000
    log_level: str = "INFO"

    # Streamlit / frontend
    streamlit_port: int = 8501
    backend_url: str = "http://127.0.0.1:8000"

    # Timeouts
    ollama_timeout: int = 600
    # Wall-clock cap for the chat graph (incl. SQL retries); the consultant
    # review step is bounded separately by consultant_timeout in job_runner.
    chat_job_max_seconds: int = 1200

    # Local storage
    data_local_dir: str = "data/local"
    data_templates_dir: str = "data/templates"

    # Anthropic external consultant (Claude)
    anthropic_api_key: str = ""
    consultant_enabled: bool = False
    consultant_model: str = "claude-opus-4-8"
    consultant_max_tokens: int = 16000
    consultant_timeout: int = 300
    consultant_max_section_chars: int = 6000
    consultant_review_chat: bool = True  # โหมด 1
    consultant_coach_onboarding: bool = True  # โหมด 2
    consultant_on_demand: bool = True  # โหมด 3
    consultant_help_when_stuck: bool = True  # โหมด 4

    @property
    def fabric_is_configured(self) -> bool:
        return all(
            [
                self.fabric_server,
                self.fabric_database,
                self.fabric_tenant_id,
                self.fabric_client_id,
                self.fabric_client_secret,
            ]
        )

    @property
    def consultant_is_enabled(self) -> bool:
        return self.consultant_enabled and bool(self.anthropic_api_key)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
