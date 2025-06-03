import duckdb
import pytest

from normalize.core.duckdb_manager import DuckDBManager


def test_duckdb_connection_opens_sets_memory_limit_and_closes() -> None:
    manager = DuckDBManager(memory_limit="1GB")
    with manager as conn:
        memory_limit = conn.execute("SELECT current_setting('memory_limit')").fetchone()[0]
        assert isinstance(memory_limit, str)
        assert memory_limit != ""
        assert conn.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(duckdb.ConnectionException):
        conn.execute("SELECT 1")
