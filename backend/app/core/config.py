"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Centralized application settings backed by environment variables."""

    app_name: str = Field(default="SAT-TRIAGE API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+psycopg://sat_triage:sat_triage_dev@localhost:5433/sat_triage",
        alias="DATABASE_URL",
    )
    db_connect_timeout: int = Field(default=2, alias="DB_CONNECT_TIMEOUT")

    jwt_secret_key: str = Field(
        default="dev-only-change-before-production",
        alias="JWT_SECRET_KEY",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    simulator_satellite_id: str = Field(default="SAT-01", alias="SIMULATOR_SATELLITE_ID")
    simulator_interval_seconds: float = Field(default=1.0, ge=0.2, le=60.0, alias="SIMULATOR_INTERVAL_SECONDS")
    simulator_nominal_voltage: float = Field(default=28.0, alias="SIMULATOR_NOMINAL_VOLTAGE")
    simulator_nominal_temperature: float = Field(default=22.5, alias="SIMULATOR_NOMINAL_TEMPERATURE")
    simulator_persist_batch_size: int = Field(default=10, ge=1, le=200, alias="SIMULATOR_PERSIST_BATCH_SIZE")

    # Phase 6: Evidence-Linked RAG & AI Copilot configuration
    runbooks_dir: str = Field(default="backend/data/runbooks", alias="RUNBOOKS_DIR")
    faiss_index_dir: str = Field(default="backend/data/faiss", alias="FAISS_INDEX_DIR")
    embedding_cache_dir: str = Field(default="backend/data/models", alias="EMBEDDING_CACHE_DIR")
    embedding_model_name: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL_NAME")
    rag_top_k: int = Field(default=5, ge=1, le=20, alias="RAG_TOP_K")
    rag_min_similarity: float = Field(default=0.56, ge=0.0, le=1.0, alias="RAG_MIN_SIMILARITY")

    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    llm_timeout_seconds: float = Field(default=25.0, ge=2.0, le=120.0, alias="LLM_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    def resolve_project_path(self, configured_path: str) -> Path:
        """Resolve a configured relative path against the repository root."""
        path = Path(configured_path)
        return path if path.is_absolute() else (ROOT_DIR / path).resolve()

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a clean list."""
        raw = self.cors_origins.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        return [
            origin.strip().strip('"').strip("'")
            for origin in raw.split(",")
            if origin.strip().strip('"').strip("'")
        ]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
