"""Sample row and sample value extraction for suggestion display."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import openpyxl
from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier
from suggestion.constants import DISPLAY_RAW_ROWS, DISPLAY_VALUES_PER_COLUMN


def read_csv_sample_rows(text: str, *, delimiter: str) -> list[list[str]]:
    """Return the first DISPLAY_RAW_ROWS rows from decoded CSV text as raw string lists."""
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for i, row in enumerate(reader):
        if i >= DISPLAY_RAW_ROWS:
            break
        rows.append(row)
    return rows


def read_excel_sample_rows(source_file: Path) -> list[list[str]]:
    """Return the first DISPLAY_RAW_ROWS rows from the first sheet as raw string lists."""
    wb = openpyxl.load_workbook(str(source_file), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows: list[list[str]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i >= DISPLAY_RAW_ROWS:
            break
        rows.append([str(cell) if cell is not None else "" for cell in row])
    wb.close()
    return rows


def read_json_sample_rows(source_file: Path) -> list[list[str]]:
    """
    Return the first DISPLAY_RAW_ROWS records from a JSON array file as raw string lists.

    Only top-level arrays of objects are supported. Each record is serialised
    as a flat list of its values for consistent display.
    """
    text = source_file.read_text(encoding="utf-8", errors="ignore")
    records: list[dict[str, object]] = json.loads(text)[:DISPLAY_RAW_ROWS]
    return [[str(v) for v in record.values()] for record in records]


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
