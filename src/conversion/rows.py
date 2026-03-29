"""Row normalization planning."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier

from conversion.models import RowPlan


def plan_rows(
    conn: DuckDBPyConnection,
    columns: list[str],
    assign_indices: bool = True,
    drop_empty_rows: bool = True,
) -> RowPlan:
    """
    Scans the table for empty rows and produces a RowPlan for the transform.

    The empty-row count determines whether the transform can use the cheap
    rowid+1 index or needs ROW_NUMBER() to close gaps after filtering.
    """
    filter_predicate: str | None = None
    rows_dropped = 0
    if drop_empty_rows:
        filter_predicate = _build_non_empty_predicate(columns)
        row = conn.execute(
            f"SELECT COUNT(*), COUNT(*) FILTER (WHERE {filter_predicate})"
            f" FROM {RAW_INPUT_TABLE_NAME}"
        ).fetchone()
        rows_before, non_empty = row  # type: ignore[misc]
        rows_dropped = rows_before - non_empty

    return RowPlan(
        filter_predicate=filter_predicate,
        assign_indices=assign_indices,
        rows_dropped=rows_dropped,
    )


def _build_non_empty_predicate(columns: list[str]) -> str:
    if not columns:
        return "FALSE"
    checks = [f"LENGTH({_stripped_value_expr(col)}) > 0" for col in columns]
    return " OR ".join(checks)


def _stripped_value_expr(column_name: str) -> str:
    raw = f"COALESCE(CAST({quote_identifier(column_name)} AS VARCHAR), '')"
    # Remove common whitespace characters without regex:
    # space (32), tab (9), newline (10), carriage return (13).
    return (
        f"REPLACE(REPLACE(REPLACE(REPLACE({raw}, CHR(32), ''), "
        "CHR(9), ''), CHR(10), ''), CHR(13), '')"
    )
