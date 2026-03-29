"""DuckDB connection lifecycle helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import TracebackType
from urllib.parse import urlparse

import duckdb
from duckdb import DuckDBPyConnection

from shared.db.sql import quote_string
from shared.settings import get_settings


def _escape_sql_string(value: str) -> str:
    return quote_string(value)[1:-1]


class DuckDBManager:
    """
    Context manager for an in-memory DuckDB connection.

    Defaults are tuned for local high-throughput batch work:
    - explicit `memory_limit`
    - dedicated temporary spill directory
    - thread count set to available CPU cores unless overridden
    """

    def __init__(
        self,
        memory_limit: str = "4GB",
        threads: int | None = None,
        database: str = ":memory:",
    ) -> None:
        self.memory_limit = memory_limit
        self.threads = threads
        self.database = database
        self._conn: DuckDBPyConnection | None = None
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> DuckDBPyConnection:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="normalize-duckdb-")
        self._conn = duckdb.connect(database=self.database)
        self._conn.execute(f"SET memory_limit='{self.memory_limit}'")
        escaped_temp_dir = self._temp_dir.name.replace("'", "''")
        self._conn.execute(f"SET temp_directory='{escaped_temp_dir}'")
        thread_count = self.threads if self.threads is not None else (os.cpu_count() or 1)
        if thread_count < 1:
            raise ValueError("threads must be >= 1")
        self._conn.execute(f"SET threads={thread_count}")
        return self._conn

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None


def configure_duckdb_s3(conn: DuckDBPyConnection) -> None:
    """Configure one DuckDB connection for S3-backed reads."""
    settings = get_settings()
    endpoint = urlparse(settings.s3_endpoint_url)
    endpoint_host = endpoint.netloc or endpoint.path
    use_ssl = endpoint.scheme == "https"

    conn.execute("LOAD httpfs")
    conn.execute(f"SET s3_endpoint='{_escape_sql_string(endpoint_host)}'")
    conn.execute(f"SET s3_access_key_id='{_escape_sql_string(settings.s3_access_key_id)}'")
    conn.execute(
        f"SET s3_secret_access_key='{_escape_sql_string(settings.s3_secret_access_key)}'"
    )
    conn.execute(f"SET s3_use_ssl={'true' if use_ssl else 'false'}")
    conn.execute("SET s3_url_style='path'")
    conn.execute("SET s3_region='auto'")


def get_duckdb_version(conn: DuckDBPyConnection) -> str:
    """Return the DuckDB version string for the active connection."""
    row = conn.execute("SELECT version()").fetchone()
    return str(row[0])  # type: ignore[index]  # version() always returns one row


def resolve_db_path(db_path: str) -> str:
    """Resolve a DuckDB database path, creating parent dirs if needed."""
    if db_path == ":memory:":
        return db_path

    db_file = Path(db_path)
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    db_file.parent.mkdir(parents=True, exist_ok=True)
    return str(db_file)
