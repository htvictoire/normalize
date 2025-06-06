"""Quality precompute materialization used after cell normalization rewrite."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.cell_normalization.sql_helpers import quote_identifier


def refresh_quality_profile_precompute(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    data_columns: Sequence[str],
) -> None:
    """
    Materialize lightweight per-column counters for quality stage.

    Stored table:
    - `_quality_profile_raw_input`
      - `column_name`
      - `row_count`
      - `nullish_count`
      - `non_null_count`
    """
    profile_table = "_quality_profile_raw_input"
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {profile_table} (
            column_name VARCHAR,
            row_count BIGINT,
            nullish_count BIGINT,
            non_null_count BIGINT
        )
        """
    )
    if not data_columns:
        return

    aggregate_exprs: list[str] = ["COUNT(*) AS row_count"]
    for column_name in data_columns:
        quoted = quote_identifier(column_name)
        aggregate_exprs.append(
            f"SUM(CASE WHEN {quoted} IS NULL THEN 1 ELSE 0 END) AS {column_name}__nullish_count"
        )
        aggregate_exprs.append(f"COUNT({quoted}) AS {column_name}__non_null_count")

    row = conn.execute(f"SELECT {', '.join(aggregate_exprs)} FROM {table_name}").fetchone()
    if row is None:
        raise RuntimeError("quality precompute query returned no rows")

    row_count = int(row[0])
    rows_for_insert: list[tuple[str, int, int, int]] = []
    offset = 1
    for column_name in data_columns:
        nullish_count = int(row[offset])
        non_null_count = int(row[offset + 1])
        offset += 2
        rows_for_insert.append((column_name, row_count, nullish_count, non_null_count))

    conn.executemany(
        f"""
        INSERT INTO {profile_table}
            (column_name, row_count, nullish_count, non_null_count)
        VALUES (?, ?, ?, ?)
        """,
        rows_for_insert,
    )
