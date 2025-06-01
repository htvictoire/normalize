"""SQL helper utilities for quality metrics queries."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from normalize.core.sql_helpers import (
    quote_identifier,
    read_columns,
    validate_identifier,
)

AUDIT_COLUMNS = {
    "_row_index",
    "_global_row_index",
    "_raw_row",
    "_parse_issues",
    "_parse_error_count",
}


def read_data_columns(conn: DuckDBPyConnection, table_name: str) -> list[str]:
    """Read non-audit columns from a table in order."""
    return [name for name in read_columns(conn, table_name) if name not in AUDIT_COLUMNS]


def column_exists(conn: DuckDBPyConnection, *, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    return column_name in read_columns(conn, table_name)


def table_exists(conn: DuckDBPyConnection, table_name: str) -> bool:
    """Check if a table exists."""
    row = conn.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = ?
        """,
        [table_name],
    ).fetchone()
    return bool(row and int(row[0]) > 0)


__all__ = [
    "validate_identifier",
    "quote_identifier",
    "read_data_columns",
    "column_exists",
    "table_exists",
]
