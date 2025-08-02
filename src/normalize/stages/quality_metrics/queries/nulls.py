"""Null-stats query helpers."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.quality_metrics.sql_helpers import quote_identifier


def read_column_null_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
) -> dict[str, dict[str, int]]:
    """Read per-column null/non-null counts from the normalized table."""
    if not columns:
        return {}
    exprs: list[str] = []
    for column_name in columns:
        quoted = quote_identifier(column_name)
        exprs.append(
            "SUM(CASE "
            f"WHEN {quoted} IS NULL THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__nullish_count"
        )
        exprs.append(f"COUNT({quoted}) AS {column_name}__non_null_count")
    row = conn.execute(f"SELECT {', '.join(exprs)} FROM {table_name}").fetchone()
    if row is None:
        raise RuntimeError("column null-stats query returned no rows")

    stats: dict[str, dict[str, int]] = {}
    offset = 0
    for column_name in columns:
        stats[column_name] = {
            "nullish_count": int(row[offset]),
            "non_null_count": int(row[offset + 1]),
        }
        offset += 2
    return stats
