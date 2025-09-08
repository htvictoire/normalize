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
    """
    Return the first DISPLAY_RAW_ROWS rows from the first sheet as raw string lists.

    openpyxl read_only=True streams rows lazily; only the rows we iterate over
    are materialised in memory.
    """
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

    Streams the file in 4 KB chunks using an incremental decoder so only one
    record plus one chunk is held in memory at a time — the full file is never
    loaded.
    """
    decoder = json.JSONDecoder()
    buf = ""
    rows: list[list[str]] = []

    with source_file.open("r", encoding="utf-8", errors="ignore") as fh:
        # Advance past the opening '['
        for chunk in iter(lambda: fh.read(4096), ""):
            buf += chunk
            idx = buf.find("[")
            if idx != -1:
                buf = buf[idx + 1 :]
                break

        # Stream-decode one record at a time
        while len(rows) < DISPLAY_RAW_ROWS:
            buf = buf.lstrip(" \t\n\r,")
            if buf.startswith("]"):
                break
            try:
                obj, end = decoder.raw_decode(buf)
                if isinstance(obj, dict):
                    rows.append([str(v) for v in obj.values()])
                buf = buf[end:]
            except json.JSONDecodeError:
                chunk = fh.read(4096)
                if not chunk:
                    break
                buf += chunk

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
