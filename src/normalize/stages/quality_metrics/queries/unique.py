"""Unique-count query helpers."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.quality_metrics.sql_helpers import quote_identifier


def read_unique_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
    approximate: bool = False,
) -> dict[str, dict[str, int]]:
    """Read per-column distinct/non-null counters.

    When ``approximate=True``, uses ``APPROX_COUNT_DISTINCT`` instead of exact
    ``COUNT(DISTINCT ...)``.  This is significantly faster on large tables
    (~3-4x speedup on 10M+ rows) with ~2% relative error.
    """
    exprs: list[str] = []
    for column_name in columns:
        quoted = quote_identifier(column_name)
        if approximate:
            exprs.append(
                f"APPROX_COUNT_DISTINCT({quoted}) "
                f"FILTER (WHERE {quoted} IS NOT NULL) "
                f"AS {column_name}__unique_non_null_count"
            )
        else:
            exprs.append(
                "COUNT(DISTINCT "
                f"{quoted}"
                ") FILTER (WHERE "
                f"{quoted}"
                f" IS NOT NULL) AS {column_name}__unique_non_null_count"
            )
        exprs.append(f"COUNT({quoted}) AS {column_name}__non_null_count")
    query = f"SELECT {', '.join(exprs)} FROM {table_name}"
    row = conn.execute(query).fetchone()
    if row is None:
        raise RuntimeError("quality stats query returned no rows")

    stats: dict[str, dict[str, int]] = {}
    offset = 0
    for column_name in columns:
        stats[column_name] = {
            "unique_non_null_count": int(row[offset]),
            "non_null_count": int(row[offset + 1]),
        }
        offset += 2
    return stats
