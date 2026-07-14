"""Runtime settings loaded from .env (prefix: NORMALIZE_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.models.operation import AiProvider


class Settings(BaseSettings):
    duckdb_memory_limit: str
    duckdb_threads: int = 4
    duckdb_cache_dir: str = "./data/duckdb"
    postgres_dsn: str
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket: str
    conversion_output_dir: str
    redis_url: str

    # Local sources must resolve within this directory; anything outside is rejected.
    local_source_root: str = "./data"
    ai_provider: AiProvider
    ai_sample_row_count: int = 50
    gemini_api_key: str = ""
    gemini_model: str

    model_config = SettingsConfigDict(
        env_prefix="NORMALIZE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process-wide settings."""
    return Settings()  # type: ignore[call-arg]
