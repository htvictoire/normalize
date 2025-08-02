"""Combined unique+parse-error query helpers."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.quality_metrics.sql_helpers import quote_identifier


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
