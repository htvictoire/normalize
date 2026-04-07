"""Pipeline-level row and column counts for profiling."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, nullish_predicate, quote_identifier
from shared.models.profiling import ColumnCounts

from profiling.aggregates import fetch_aggregate_int_row, group_int_values


@dataclass(frozen=True)
class ProfilingStats:
    """Profiling row counts plus per-column null/nullish counts, keyed by column name."""

    row_count: int
    empty_row_count: int
    column_counts: dict[str, ColumnCounts]


def compute_profiling_stats(
    conn: DuckDBPyConnection,
    columns: list[str],
    null_tokens: tuple[str, ...],
) -> ProfilingStats:
    """Return row counts and per-column null counts in a single table scan."""
    if not columns:
        row_count = execute_scalar(conn, f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME}")
        return ProfilingStats(row_count=row_count, empty_row_count=row_count, column_counts={})

    per_col_exprs: list[str] = []
    empty_predicates: list[str] = []

    for col_name in columns:
        quoted = quote_identifier(col_name)
        structural = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') IS NULL"
        nullish = nullish_predicate(quoted, null_tokens)
        per_col_exprs.append(f"COUNT(*) FILTER (WHERE {structural})")
        per_col_exprs.append(f"COUNT(*) FILTER (WHERE {nullish})")
        empty_predicates.append(nullish)

    empty_expr = f"COUNT(*) FILTER (WHERE {' AND '.join(empty_predicates)})"
    query = (
        f"SELECT COUNT(*), {empty_expr}, {', '.join(per_col_exprs)}"
        f" FROM {RAW_INPUT_TABLE_NAME}"
    )
    row = fetch_aggregate_int_row(conn, query)
    row_count, empty_row_count, *per_column_counts = row

    column_counts: dict[str, ColumnCounts] = {}
    count_pairs = group_int_values(
        per_column_counts,
        group_size=2,
        expected_groups=len(columns),
    )
    for col_name, (null_count, nullish_count) in zip(columns, count_pairs, strict=True):
        column_counts[col_name] = ColumnCounts(
            null_count=null_count,
            nullish_count=nullish_count,
            non_null_count=row_count - null_count,
            non_nullish_count=row_count - nullish_count,
        )

    return ProfilingStats(
        row_count=row_count,
        empty_row_count=empty_row_count,
        column_counts=column_counts,
    )
