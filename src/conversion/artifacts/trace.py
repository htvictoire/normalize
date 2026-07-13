"""Trace parquet query/build/write helpers."""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import (
    quote_identifier,
    quote_string,
)

from conversion.constants import (
    PARQUET_COPY_OPTIONS,
    PARSE_ISSUES_COLUMN,
    RAW_ROW_COLUMN,
    ROW_INDEX_COLUMN,
)


def build_trace_query(
    data_columns: list[str],
    has_row_index: bool,
    has_full_raw_row: bool,
    sparse: bool = False,
    row_pre_filter: str | None = None,
) -> str:
    """Build wide-to-long trace SQL query with one output row per input cell.

    ``raw_value`` for a failing cell always comes from ``_parse_issues``, which
    carries the original text alongside the issue code. When ``has_full_raw_row``
    is set, cells that parsed successfully additionally resolve their original
    from ``_raw_row``.

    When sparse=True, only emit rows where an issue was detected (or, under full
    lineage, where the value changed).

    ``row_pre_filter`` is an optional SQL predicate applied *before* UNPIVOT in the
    base CTE, allowing the caller to skip entire rows cheaply (e.g. only process
    rows with ``_parse_error_count > 0``).
    """
    row_index_expr = ROW_INDEX_COLUMN if has_row_index else "(rowid + 1)::BIGINT"
    casted_columns = ", ".join(
        f"CAST({quote_identifier(column_name)} AS VARCHAR) AS {quote_identifier(column_name)}"
        for column_name in data_columns
    )
    unpivot_columns = ", ".join(quote_identifier(column_name) for column_name in data_columns)
    extra_base_columns = [PARSE_ISSUES_COLUMN]
    if has_full_raw_row:
        extra_base_columns.append(RAW_ROW_COLUMN)
    extra_projection = ", " + ", ".join(extra_base_columns)

    issue_raw_expr = (
        f"JSON_EXTRACT_STRING({PARSE_ISSUES_COLUMN}, '$.' || column_name || '.raw')"
    )
    issue_expr = (
        f"JSON_EXTRACT_STRING({PARSE_ISSUES_COLUMN}, '$.' || column_name || '.code')"
    )
    raw_expr = (
        f"COALESCE({issue_raw_expr}, "
        f"JSON_EXTRACT_STRING({RAW_ROW_COLUMN}, '$.' || column_name))"
        if has_full_raw_row
        else issue_raw_expr
    )

    # Sparse filter: only cells that failed, plus — under full lineage — cells
    # whose value the normalizer actually changed.
    sparse_filter = ""
    if sparse:
        conditions = [f"{issue_expr} IS NOT NULL"]
        if has_full_raw_row:
            conditions.append(
                f"JSON_EXTRACT_STRING({RAW_ROW_COLUMN}, '$.' || column_name) "
                "IS DISTINCT FROM CAST(normalized_value AS VARCHAR)"
            )
        sparse_filter = "WHERE " + " OR ".join(conditions)

    base_where = f" WHERE {row_pre_filter}" if row_pre_filter else ""
    return (
        "WITH base AS ("
        "SELECT "
        f"{row_index_expr} AS row_index, "
        f"{casted_columns}{extra_projection} "
        f"FROM {RAW_INPUT_TABLE_NAME}{base_where}"
        "), unpivoted AS ("
        "SELECT row_index, column_name, normalized_value"
        f"{extra_projection} "
        "FROM base "
        f"UNPIVOT INCLUDE NULLS (normalized_value FOR column_name IN ({unpivot_columns}))"
        ") "
        "SELECT "
        "row_index, "
        "column_name, "
        f"{raw_expr} AS raw_value, "
        "normalized_value, "
        "'normalization' AS applied_rules, "
        f"{issue_expr} AS issue_codes "
        "FROM unpivoted"
        f" {sparse_filter}"
    )


def write_trace_parquet(
    conn: DuckDBPyConnection,
    trace_path: Path,
    data_columns: list[str],
    has_row_index: bool,
    has_full_raw_row: bool,
    sparse: bool = False,
    row_pre_filter: str | None = None,
) -> None:
    """Export cell-level trace parquet."""
    trace_query = build_trace_query(
        data_columns=data_columns,
        has_row_index=has_row_index,
        has_full_raw_row=has_full_raw_row,
        sparse=sparse,
        row_pre_filter=row_pre_filter,
    )
    conn.execute(
        "COPY ("
        + trace_query
        + ") TO "
        + quote_string(str(trace_path))
        + " "
        + PARQUET_COPY_OPTIONS
    )
