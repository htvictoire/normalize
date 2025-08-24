"""Reservoir sampling of column values from a DuckDB table."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from shared.utils.values import normalize_cell_value
from suggestion.constants import (
    INFERENCE_RESERVOIR_ROWS,
    INFERENCE_SAMPLE_SEED,
    INFERENCE_SAMPLES_PER_COLUMN,
)


def sample_column_values(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
) -> dict[str, list[str]]:
    """Sample non-null values per column from a reservoir sample of the table."""
    sql = (
        f"SELECT * FROM {table_name} USING SAMPLE "
        f"reservoir({INFERENCE_RESERVOIR_ROWS} ROWS) REPEATABLE ({INFERENCE_SAMPLE_SEED})"
    )
    sampled_rows = conn.execute(sql).fetchall()
    result: dict[str, list[str]] = {col: [] for col in columns}
    for row in sampled_rows:
        for index, col_name in enumerate(columns):
            if len(result[col_name]) >= INFERENCE_SAMPLES_PER_COLUMN:
                continue
            value = normalize_cell_value(row[index])
            if value is not None:
                result[col_name].append(value)
    return result
