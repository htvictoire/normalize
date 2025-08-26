"""Null/nullish count computation for profiling — delegates to shared query."""

from __future__ import annotations

from collections.abc import Mapping

from duckdb import DuckDBPyConnection

from shared.db.sql import compute_column_counts
from shared.models.profiling import ColumnCounts


def compute_null_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    position_to_name: Mapping[str, str],
    null_tokens: tuple[str, ...],
) -> tuple[int, dict[str, ColumnCounts]]:
    """Return (row_count, {position_key: ColumnCounts}) using confirmed null tokens."""
    return compute_column_counts(
        conn,
        table_name=table_name,
        position_to_name=position_to_name,
        null_tokens=null_tokens,
    )
