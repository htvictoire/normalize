"""Sample row and sample value extraction for suggestion display."""

from __future__ import annotations

import csv

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier
from suggestion.constants import DISPLAY_RAW_ROWS, DISPLAY_VALUES_PER_COLUMN


def read_sample_rows(text: str, *, delimiter: str) -> list[list[str]]:
    """Return the first DISPLAY_RAW_ROWS rows from decoded text as raw string lists."""
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for i, row in enumerate(reader):
        if i >= DISPLAY_RAW_ROWS:
            break
        rows.append(row)
    return rows


def read_sample_values(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    position_to_name: dict[str, str],
) -> dict[str, list[str]]:
    """
    Return up to DISPLAY_VALUES_PER_COLUMN non-null values per column, keyed by position.

    Empty and whitespace-only cells are excluded. Each column is fetched
    independently via UNION ALL so sparse columns are not crowded out by
    denser ones.
    """
    if not position_to_name:
        return {}

    positions = list(position_to_name.keys())
    parts: list[str] = []
    for i, col_name in enumerate(position_to_name.values()):
        quoted = quote_identifier(col_name)
        nullish = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '')"
        parts.append(
            f"(SELECT {i} AS col_idx, {nullish} AS val "
            f"FROM {table_name} WHERE {nullish} IS NOT NULL "
            f"LIMIT {DISPLAY_VALUES_PER_COLUMN})"
        )

    rows = conn.execute(" UNION ALL ".join(parts)).fetchall()

    result: dict[str, list[str]] = {pos: [] for pos in positions}
    for col_idx, val in rows:
        if val is not None:
            result[positions[col_idx]].append(str(val))
    return result
