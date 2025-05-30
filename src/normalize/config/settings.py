"""Runtime settings for the Phase 1 pipeline."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Minimal settings needed by currently implemented stages.

    Environment variable prefix: `NORMALIZE_`
    """

    duckdb_memory_limit: str = "4GB"

    model_config = SettingsConfigDict(
        env_prefix="NORMALIZE_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process-wide settings."""
    return Settings()
