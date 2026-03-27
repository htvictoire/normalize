"""String profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.profiling import ColumnCounts, StringColumnProfile


def compute_string_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
) -> StringColumnProfile:
    """Count distinct values and measure character length distribution."""
    quoted = quote_identifier(column_name)
    value_expr = f"TRIM(CAST({quoted} AS VARCHAR))"
    nullish = nullish_predicate(quoted, null_tokens)

    row = conn.execute(
        f"SELECT COUNT(DISTINCT {value_expr}), "
        f"COALESCE(MIN(LENGTH({value_expr})), 0), "
        f"COALESCE(MAX(LENGTH({value_expr})), 0) "
        f"FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish})"
    ).fetchone()
    distinct_count = int(row[0])  # type: ignore[index]
    min_length = int(row[1])  # type: ignore[index]
    max_length = int(row[2])  # type: ignore[index]

    non_nullish = counts.non_nullish_count
    distinct_ratio = 1.0 if non_nullish <= 0 else (distinct_count / non_nullish)

    return StringColumnProfile(
        distinct_count=distinct_count,
        distinct_ratio=distinct_ratio,
        min_length=min_length,
        max_length=max_length,
    )
