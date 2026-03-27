"""Normalized parquet export helpers."""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier, quote_string, validate_identifier

from conversion.stages.artifact_materialization.constants import (
    AUDIT_EXCLUDED_FROM_DATA,
    AUDIT_OUTPUT_COLUMNS,
)


def build_export_columns(columns: list[str]) -> list[str]:
    """Return output schema order: data columns first, then known audit columns."""
    data_columns = [column for column in columns if column not in AUDIT_EXCLUDED_FROM_DATA]
    audit_columns = [column for column in AUDIT_OUTPUT_COLUMNS if column in columns]
    return data_columns + audit_columns


def write_normalized_parquet(
    conn: DuckDBPyConnection,
    normalized_path: Path,
    export_columns: list[str],
) -> None:
    """Export table directly to parquet with selected columns in order.

    Skips temp table materialization - writes COPY query directly from source.
    """
    validate_identifier(RAW_INPUT_TABLE_NAME)
    selected = ", ".join(quote_identifier(col) for col in export_columns)
    query = f"SELECT {selected} FROM {RAW_INPUT_TABLE_NAME}"
    conn.execute(
        "COPY ("
        + query
        + ") TO "
        + quote_string(str(normalized_path))
        + " (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
