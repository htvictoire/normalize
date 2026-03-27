"""Pipeline-level row and column counts for profiling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import (
    compute_column_counts,
    execute_scalar,
    nullish_predicate,
    quote_identifier,
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
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...],
) -> ProfilingStats:
    """Return row-level profiling counts for the current DuckDB table."""
    columns = list(position_to_name.values())
    result = compute_column_counts(
        conn,
        position_to_name=position_to_name,
        null_tokens=null_tokens,
    )
    if not columns:
        return ProfilingStats(
            row_count=result.row_count,
            empty_row_count=result.row_count,
            column_counts=result.column_counts,
        )

    predicates = [nullish_predicate(quote_identifier(column), null_tokens) for column in columns]
    empty_row_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME} WHERE {' AND '.join(predicates)}",
    )
    return ProfilingStats(
        row_count=result.row_count,
        empty_row_count=empty_row_count,
        column_counts=result.column_counts,
    )
