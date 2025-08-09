"""Profiling helpers for suggestion output."""

from __future__ import annotations

from collections.abc import Mapping

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier
from shared.models.profiling import ProfilingColumnStats, ProfilingStats


def compute_profiling_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    position_to_name: Mapping[str, str],
) -> ProfilingStats:
    """Compute row_count and per-position null/non-null stats."""
    if not position_to_name:
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        row_count = 0 if row is None else int(row[0])
        return ProfilingStats(row_count=row_count, columns={})

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
        return ProfilingStats(row_count=0, columns={})

    row_count = int(row[0])
    columns: dict[str, ProfilingColumnStats] = {}
    for index, position_key in enumerate(position_to_name.keys()):
        nullish_count = int(row[index + 1])
        columns[position_key] = ProfilingColumnStats(
            nullish_count=nullish_count,
            non_null_count=max(row_count - nullish_count, 0),
        )
    return ProfilingStats(row_count=row_count, columns=columns)
