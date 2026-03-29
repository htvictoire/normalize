"""Normalized parquet export helpers."""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier, quote_string

from conversion.constants import AUDIT_OUTPUT_COLUMNS, AUDIT_RECORD_COLUMNS


def build_export_columns(data_columns: list[str], assign_indices: bool) -> list[str]:
    """Return output schema order: data columns first, then audit columns."""
    audit = AUDIT_OUTPUT_COLUMNS if assign_indices else AUDIT_RECORD_COLUMNS
    return data_columns + list(audit)


def write_normalized_parquet(
    conn: DuckDBPyConnection,
    normalized_path: Path,
    export_columns: list[str],
) -> None:
    """Export table directly to parquet with selected columns in order.

    Skips temp table materialization - writes COPY query directly from source.
    """
    selected = ", ".join(quote_identifier(col) for col in export_columns)
    query = f"SELECT {selected} FROM {RAW_INPUT_TABLE_NAME}"
    conn.execute(
        "COPY ("
        + query
        + ") TO "
        + quote_string(str(normalized_path))
        + " (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
