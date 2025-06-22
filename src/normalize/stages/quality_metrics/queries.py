"""DuckDB query helpers for quality metrics stage."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.quality_metrics.sql_helpers import (
    column_exists,
    quote_identifier,
)


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


def read_detailed_column_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
    approximate: bool = False,
) -> dict[str, dict[str, int]]:
    """
    Read unique/non-null/parse-error counters in one table scan.

    Returned keys per column:
    - unique_non_null_count
    - non_null_count
    - parse_error_count

    When ``approximate=True``, uses ``APPROX_COUNT_DISTINCT`` for the unique
    count (~2% relative error, significantly faster on large tables).
    """
    if not columns:
        return {}
    exprs: list[str] = []
    for column_name in columns:
        quoted = quote_identifier(column_name)
        json_path = "$." + column_name
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
        exprs.append(
            "SUM(CASE "
            f"WHEN JSON_EXTRACT_STRING(_parse_issues, '{json_path}') IS NULL THEN 0 "
            "ELSE 1 END) "
            f"AS {column_name}__parse_error_count"
        )
    query = f"SELECT {', '.join(exprs)} FROM {table_name}"
    row = conn.execute(query).fetchone()
    if row is None:
        raise RuntimeError("detailed column stats query returned no rows")

    stats: dict[str, dict[str, int]] = {}
    offset = 0
    for column_name in columns:
        stats[column_name] = {
            "unique_non_null_count": int(row[offset]),
            "non_null_count": int(row[offset + 1]),
            "parse_error_count": int(row[offset + 2]),
        }
        offset += 3
    return stats


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


def read_precomputed_total_parse_error_cells(conn: DuckDBPyConnection) -> int:
    """Read total parse error cells from `_quality_profile_raw_input` precompute table."""
    row = conn.execute(
        "SELECT COALESCE(MAX(total_parse_error_cells), 0) FROM _quality_profile_raw_input"
    ).fetchone()
    return 0 if row is None else int(row[0])


def read_precomputed_row_count(conn: DuckDBPyConnection) -> int:
    """Read row_count from `_quality_profile_raw_input` precompute table."""
    row = conn.execute(
        "SELECT COALESCE(MAX(row_count), 0) FROM _quality_profile_raw_input"
    ).fetchone()
    return 0 if row is None else int(row[0])


def read_precomputed_total_nullish_cells(conn: DuckDBPyConnection) -> int:
    """Read total nullish cells from `_quality_profile_raw_input` precompute table."""
    row = conn.execute(
        "SELECT COALESCE(SUM(nullish_count), 0) FROM _quality_profile_raw_input"
    ).fetchone()
    return 0 if row is None else int(row[0])


def read_precomputed_column_null_stats(
    conn: DuckDBPyConnection,
) -> dict[str, dict[str, int]]:
    """Read per-column null/non-null counters from precomputed quality profile table."""
    rows = conn.execute(
        """
        SELECT column_name, nullish_count, non_null_count
        FROM _quality_profile_raw_input
        ORDER BY column_name
        """
    ).fetchall()
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        result[str(row[0])] = {
            "nullish_count": int(row[1]),
            "non_null_count": int(row[2]),
        }
    return result
