"""SQL helper utilities used by shared profiling."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from normalize.core.sql_helpers import (
    quote_identifier,
    quote_string,
    read_columns,
    validate_identifier,
)
from normalize.stages.shared_profiling.contracts import AUDIT_COLUMNS


def read_data_columns(conn: DuckDBPyConnection, table_name: str) -> list[str]:
    """Read ordered non-audit columns from a table."""
    return [name for name in read_columns(conn, table_name) if name not in AUDIT_COLUMNS]


def table_exists(conn: DuckDBPyConnection, table_name: str) -> bool:
    """Check if a main-schema table exists."""
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    ).fetchone()
    return bool(row and int(row[0]) > 0)


__all__ = [
    "quote_identifier",
    "quote_string",
    "read_data_columns",
    "table_exists",
    "validate_identifier",
]
