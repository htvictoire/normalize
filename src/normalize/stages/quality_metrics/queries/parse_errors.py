"""Parse-error query helpers."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.quality_metrics.sql_helpers import column_exists


def read_parse_error_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
) -> dict[str, int]:
    """Read per-column parse-error counters from `_parse_issues` JSON."""
    if not columns:
        return {}
    exprs: list[str] = []
    for column_name in columns:
        json_path = "$." + column_name
        exprs.append(
            "SUM(CASE "
            f"WHEN JSON_EXTRACT_STRING(_parse_issues, '{json_path}') IS NULL THEN 0 "
            "ELSE 1 END) "
            f"AS {column_name}__parse_error_count"
        )
    query = f"SELECT {', '.join(exprs)} FROM {table_name}"
    row = conn.execute(query).fetchone()
    if row is None:
        raise RuntimeError("parse-error query returned no rows")

    counts: dict[str, int] = {}
    for index, column_name in enumerate(columns):
        counts[column_name] = int(row[index])
    return counts


def read_total_parse_error_cells(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
) -> int:
    """Read total parse-error cells, preferring row-level counter when present."""
    if column_exists(conn, table_name=table_name, column_name="_parse_error_count"):
        row = conn.execute(
            f"SELECT COALESCE(SUM(_parse_error_count), 0) FROM {table_name}"
        ).fetchone()
        return 0 if row is None else int(row[0])

    per_column = read_parse_error_stats(conn, table_name=table_name, columns=columns)
    return sum(per_column.values())
