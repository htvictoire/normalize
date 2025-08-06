from shared.settings import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.duckdb_memory_limit == "4GB"


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("NORMALIZE_DUCKDB_MEMORY_LIMIT", "2GB")
    settings = Settings()
    assert settings.duckdb_memory_limit == "2GB"
