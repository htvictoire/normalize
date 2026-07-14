"""Trace parquet query/build/write helpers."""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import (
    quote_identifier,
    quote_string,
)
from shared.models.operation import TraceMode

from conversion.constants import (
    PARQUET_COPY_OPTIONS,
    PARSE_ISSUES_COLUMN,
    RAW_ROW_COLUMN,
    ROW_INDEX_COLUMN,
)


def build_trace_query(
    data_columns: list[str],
    trace_mode: TraceMode,
    has_raw_row: bool,
    row_pre_filter: str | None = None,
) -> str:
    """Build wide-to-long trace SQL query with one output row per input cell.

    ``raw_value`` for a failing cell always comes from ``_parse_issues``, which
    carries the original text alongside the issue code. When ``has_raw_row`` is
    set, cells that parsed successfully additionally resolve their original from
    ``_raw_row``.

    ``trace_mode`` selects which cells are emitted: ``"issues"`` (failed),
    ``"changes"`` (parsed but transformed), ``"full"`` (all). The emitted set is
    the union of the selected scopes.

    ``row_pre_filter`` is an optional SQL predicate applied *before* UNPIVOT in the
    base CTE, allowing the caller to skip entire rows cheaply (e.g. only process
    rows with ``_parse_error_count > 0``).
    """
    row_index_expr = ROW_INDEX_COLUMN
    casted_columns = ", ".join(
        f"CAST({quote_identifier(column_name)} AS VARCHAR) AS {quote_identifier(column_name)}"
        for column_name in data_columns
    )
    unpivot_columns = ", ".join(quote_identifier(column_name) for column_name in data_columns)
    extra_base_columns = [PARSE_ISSUES_COLUMN]
    if has_raw_row:
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
        if has_raw_row
        else issue_raw_expr
    )

    scope_filter = ""
    if "full" not in trace_mode:
        conditions: list[str] = []
        if "issues" in trace_mode:
            conditions.append(f"{issue_expr} IS NOT NULL")
        if "changes" in trace_mode:
            conditions.append(
                f"({issue_expr} IS NULL AND "
                f"JSON_EXTRACT_STRING({RAW_ROW_COLUMN}, '$.' || column_name) "
                "IS DISTINCT FROM CAST(normalized_value AS VARCHAR))"
            )
        scope_filter = "WHERE " + " OR ".join(conditions)

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
        f"{issue_expr} AS issue_codes "
        "FROM unpivoted"
        f" {scope_filter}"
    )


def write_trace_parquet(
    conn: DuckDBPyConnection,
    trace_path: Path,
    data_columns: list[str],
    trace_mode: TraceMode,
    has_raw_row: bool,
    row_pre_filter: str | None = None,
) -> None:
    """Export cell-level trace parquet."""
    trace_query = build_trace_query(
        data_columns=data_columns,
        trace_mode=trace_mode,
        has_raw_row=has_raw_row,
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
