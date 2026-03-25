"""Pipeline-level row and column counts for profiling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.db.sql import (
    compute_column_counts,
    execute_scalar,
    nullish_predicate,
    quote_identifier,
    read_columns,
    validate_identifier,
)
from shared.models.profiling import ColumnCounts


@dataclass(frozen=True)
class ProfilingStats:
    """Profiling row counts plus per-column null/nullish counts."""

    row_count: int
    empty_row_count: int
    column_counts: dict[str, ColumnCounts]


def compute_profiling_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...],
) -> ProfilingStats:
    """Return row-level profiling counts for the current DuckDB table."""
    validate_identifier(table_name)
    columns = read_columns(conn, table_name)
    row_count, column_counts = compute_column_counts(
        conn,
        table_name=table_name,
        position_to_name=position_to_name,
        null_tokens=null_tokens,
    )
    if not columns:
        return ProfilingStats(
            row_count=row_count,
            empty_row_count=row_count,
            column_counts=column_counts,
        )

    predicates = [nullish_predicate(quote_identifier(column), null_tokens) for column in columns]
    empty_row_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM {table_name} WHERE {' AND '.join(predicates)}",
    )
    return ProfilingStats(
        row_count=row_count,
        empty_row_count=empty_row_count,
        column_counts=column_counts,
    )

