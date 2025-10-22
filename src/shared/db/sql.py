"""Shared SQL helper utilities used across stages."""

from __future__ import annotations

import re
from collections.abc import Mapping

from duckdb import DuckDBPyConnection

from shared.models.profiling import ColumnCounts


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


def execute_scalar(conn: DuckDBPyConnection, sql: str) -> int:
    """Execute a query returning a single integer scalar (e.g. COUNT)."""
    return int(conn.execute(sql).fetchall()[0][0])


def read_columns(conn: DuckDBPyConnection, table_name: str) -> list[str]:
    """Read ordered table column names from DuckDB."""
    validate_identifier(table_name)
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return [str(row[1]) for row in rows]


def nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    """Build a SQL boolean expression that is true for structural and semantic nulls."""
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized = sorted({t.strip().lower() for t in null_tokens if t.strip()})
    if not normalized:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(t) for t in normalized)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"


def compute_column_counts(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...] = (),
) -> tuple[int, dict[str, ColumnCounts]]:
    """Return (row_count, {position_key: ColumnCounts}) in a single query.

    null_tokens drives the nullish count — pass inferred tokens at suggestion
    time, confirmed tokens at profiling time.
    """
    if not position_to_name:
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        return (0 if row is None else int(row[0])), {}

    exprs: list[str] = []
    for index, column_name in enumerate(position_to_name.values()):
        quoted = quote_identifier(column_name)
        structural = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') IS NULL"
        nullish = nullish_predicate(quoted, null_tokens)
        exprs.append(
            f"COALESCE(SUM(CASE WHEN {structural} THEN 1 ELSE 0 END), 0) AS __c{index}_null"
        )
        exprs.append(
            f"COALESCE(SUM(CASE WHEN {nullish} THEN 1 ELSE 0 END), 0) AS __c{index}_nullish"
        )

    query = f"SELECT COUNT(*) AS row_count, {', '.join(exprs)} FROM {table_name}"
    row = conn.execute(query).fetchone()
    if row is None:
        return 0, {}

    row_count = int(row[0])
    counts: dict[str, ColumnCounts] = {}
    for index, position_key in enumerate(position_to_name.keys()):
        null_count = int(row[1 + index * 2])
        nullish_count = int(row[1 + index * 2 + 1])
        counts[position_key] = ColumnCounts(
            null_count=null_count,
            nullish_count=nullish_count,
            non_null_count=max(row_count - null_count, 0),
            non_nullish_count=max(row_count - nullish_count, 0),
        )
    return row_count, counts
