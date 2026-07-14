"""Normalized parquet export helpers."""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier, quote_string

from conversion.constants import (
    AUDIT_INDEX_COLUMNS,
    PARQUET_COPY_OPTIONS,
    PARSE_ISSUES_COLUMN,
    RAW_ROW_COLUMN,
)


def build_export_columns(
    data_columns: list[str],
    full_raw_row: bool,
) -> list[str]:
    """Return output schema order: data columns first, then audit columns.

    ``_row_index`` is always exported: it is the trace's join key, so the trace
    can never be reliably tied back to the normalized rows without it.

    _raw_row is exported only when full_raw_row is set. Publishing the column while the
    option is off advertises per-cell lineage the artifact does not carry — a consumer
    reading the schema would conclude every original was preserved.
    """
    audit: list[str] = list(AUDIT_INDEX_COLUMNS)
    if full_raw_row:
        audit.append(RAW_ROW_COLUMN)
    audit.append(PARSE_ISSUES_COLUMN)
    return data_columns + audit


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
        + " "
        + PARQUET_COPY_OPTIONS
    )
