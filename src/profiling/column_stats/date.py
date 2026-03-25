"""Date profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import execute_scalar, nullish_predicate, quote_identifier, quote_string
from shared.models.profiling import ColumnCounts, DateColumnProfile


def compute_date_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    date_format: str,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
) -> DateColumnProfile:
    """Count rows parseable by configured date format."""
    quoted = quote_identifier(column_name)
    if date_format == "EXCEL_SERIAL":
        date_expr = f"(DATE '1899-12-30' + TRY_CAST({quoted} AS INTEGER))"
    else:
        date_expr = f"TRY_CAST(TRY_STRPTIME({quoted}, {quote_string(date_format)}) AS DATE)"

    nullish = nullish_predicate(quoted, null_tokens)
    format_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) AND {date_expr} IS NOT NULL",
    )

    non_nullish = counts.non_nullish_count
    format_match_ratio = 1.0 if non_nullish <= 0 else (format_match_count / non_nullish)
    return DateColumnProfile(
        format_match_count=format_match_count,
        format_match_ratio=format_match_ratio,
    )
