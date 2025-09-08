"""Infer ExcelSourceFormat by probing the first sheet with openpyxl."""

from __future__ import annotations

from pathlib import Path

import openpyxl

from shared.models.operation import ExcelSourceFormat
from suggestion.constants import HEADER_SCAN_ROWS
from suggestion.source_format.utils import looks_numeric


def _is_likely_header_row(row: tuple[object, ...]) -> bool:
    """True when the row has non-null, all-unique values with no numeric entries."""
    values = [str(cell).strip() for cell in row if cell is not None]
    if not values:
        return False
    return not any(looks_numeric(v) for v in values) and len(set(values)) == len(values)


def _detect_header_row(rows: list[tuple[object, ...]]) -> int | None:
    """Return the 1-based header row index, or None when no header is detected."""
    for i, row in enumerate(rows):
        if _is_likely_header_row(row):
            return i + 1
    return None


def infer_excel_source_format(source_file: Path) -> ExcelSourceFormat:
    """Probe the first sheet of an Excel file to detect the header row."""
    wb = openpyxl.load_workbook(str(source_file), read_only=True, data_only=True)
    ws = wb.worksheets[0]

    first_rows: list[tuple[object, ...]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i >= HEADER_SCAN_ROWS:
            break
        first_rows.append(row)

    wb.close()

    header_row_index = _detect_header_row(first_rows)
    return ExcelSourceFormat(
        header_mode="present" if header_row_index is not None else "absent",
        header_row_index=header_row_index,
    )
