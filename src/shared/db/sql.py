"""Shared SQL helper utilities used across stages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.models.profiling import ColumnCountResult, ColumnCounts


def quote_identifier(identifier: str) -> str:
    """Return SQL-quoted identifier with escaping."""
    return '"' + identifier.replace('"', '""') + '"'


def quote_string(value: str) -> str:
    """Return SQL single-quoted string with escaping."""
    return "'" + value.replace("'", "''") + "'"


def execute_scalar(conn: DuckDBPyConnection, sql: str) -> int:
    """Execute a query returning a single integer scalar (e.g. COUNT)."""
    return int(conn.execute(sql).fetchall()[0][0])


def read_relation_columns(conn: DuckDBPyConnection, table_name: str) -> list[str]:
    """Read ordered column names from one explicit DuckDB relation."""
    rows = conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    return [str(row[1]) for row in rows]


def read_columns(conn: DuckDBPyConnection) -> list[str]:
    """Read ordered column names from the working raw-input table."""
    return read_relation_columns(conn, RAW_INPUT_TABLE_NAME)


def normalize_tokens(tokens: Sequence[str]) -> tuple[str, ...]:
    """Return sorted, deduplicated, stripped, lower-cased tokens."""
    return tuple(sorted({token.strip().lower() for token in tokens if token.strip()}))


def nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    """Build a SQL boolean expression that is true for structural and semantic nulls."""
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized = normalize_tokens(null_tokens)
    if not normalized:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(t) for t in normalized)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"


def _build_column_count_query(
    relation_expr: str,
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...],
) -> str:
    if not position_to_name:
        return f"SELECT COUNT(*) AS row_count FROM {relation_expr}"

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

    return f"SELECT COUNT(*) AS row_count, {', '.join(exprs)} FROM {relation_expr}"


def _column_counts_from_row(
    row: Sequence[object],
    position_to_name: Mapping[str, str],
) -> ColumnCountResult:
    row_count = cast(int, row[0])
    counts: dict[str, ColumnCounts] = {}
    for index, position_key in enumerate(position_to_name.keys()):
        null_count = cast(int, row[1 + index * 2])
        nullish_count = cast(int, row[1 + index * 2 + 1])
        counts[position_key] = ColumnCounts(
            null_count=null_count,
            nullish_count=nullish_count,
            non_null_count=row_count - null_count,
            non_nullish_count=row_count - nullish_count,
        )
    return ColumnCountResult(row_count=row_count, column_counts=counts)


def compute_column_counts_from_relation(
    conn: DuckDBPyConnection,
    relation_expr: str,
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...] = (),
    params: Sequence[object] = (),
) -> ColumnCountResult:
    """Return ColumnCountResult from any DuckDB relation expression."""
    query = _build_column_count_query(
        relation_expr,
        position_to_name,
        null_tokens,
    )
    row = cast("tuple[object, ...]", conn.execute(query, params).fetchone())
    return _column_counts_from_row(row, position_to_name)


def compute_column_counts(
    conn: DuckDBPyConnection,
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...] = (),
) -> ColumnCountResult:
    """Return ColumnCountResult from the working raw-input table."""
    return compute_column_counts_from_relation(
        conn,
        RAW_INPUT_TABLE_NAME,
        position_to_name,
        null_tokens,
    )

