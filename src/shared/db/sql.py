"""Shared SQL helper utilities used across stages."""

from __future__ import annotations

import re

from duckdb import DuckDBPyConnection


def validate_identifier(identifier: str) -> None:
    """Validate SQL identifiers used in dynamic SQL."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")


def quote_identifier(identifier: str) -> str:
    """Return SQL-quoted identifier with escaping."""
    return '"' + identifier.replace('"', '""') + '"'


def quote_string(value: str) -> str:
    """Return SQL single-quoted string with escaping."""
    return "'" + value.replace("'", "''") + "'"


def read_columns(conn: DuckDBPyConnection, table_name: str) -> list[str]:
    """Read ordered table column names from DuckDB."""
    validate_identifier(table_name)
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return [str(row[1]) for row in rows]
