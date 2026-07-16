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
    fabric_max_rows: int = 100

    # Ollama (native Windows defaults)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:14b"
    ollama_model_analyst: str = ""
    ollama_model_ba: str = ""

    # FastAPI
    fastapi_host: str = "127.0.0.1"
    fastapi_port: int = 8000
    log_level: str = "INFO"

    # Streamlit / frontend
    streamlit_port: int = 8501
    backend_url: str = "http://127.0.0.1:8000"

    # Timeouts
    ollama_timeout: int = 600
    compose_http_timeout: int = 600

    # Local storage
    data_local_dir: str = "data/local"
    data_templates_dir: str = "data/templates"

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
