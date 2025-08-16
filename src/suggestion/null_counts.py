"""Null/non-null count computation for suggestion output."""

from __future__ import annotations

from collections.abc import Mapping

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier


def compute_null_counts(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    position_to_name: Mapping[str, str],
) -> tuple[int, dict[str, tuple[int, int]]]:
    """Return (row_count, {position_key: (null_count, non_null_count)})."""
    if not position_to_name:
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        return (0 if row is None else int(row[0])), {}

    nullish_exprs: list[str] = []
    for index, column_name in enumerate(position_to_name.values()):
        quoted = quote_identifier(column_name)
        base_expr = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '')"
        nullish_exprs.append(
            f"SUM(CASE WHEN {base_expr} IS NULL THEN 1 ELSE 0 END) AS __c{index}_nullish"
        )
    query = f"SELECT COUNT(*) AS row_count, {', '.join(nullish_exprs)} FROM {table_name}"
    row = conn.execute(query).fetchone()
    if row is None:
        return 0, {}

    row_count = int(row[0])
    counts: dict[str, tuple[int, int]] = {}
    for index, position_key in enumerate(position_to_name.keys()):
        null_count = int(row[index + 1])
        non_null_count = max(row_count - null_count, 0)
        counts[position_key] = (null_count, non_null_count)
    return row_count, counts
