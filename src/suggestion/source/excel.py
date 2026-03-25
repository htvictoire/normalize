"""Excel source helpers for suggestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl

from shared.models.operation import ExcelSourceFormat
from suggestion.constants import DISPLAY_RAW_ROWS, HEADER_SCAN_ROWS
from suggestion.source.heuristics import looks_numeric


def _has_visible_value(cell: object) -> bool:
    if cell is None:
        return False
    return bool(str(cell).strip())


def _row_to_strings(row: tuple[object, ...]) -> list[str]:
    return [str(cell) if cell is not None else "" for cell in row]


def _is_likely_header_row(row: tuple[object, ...]) -> bool:
    values = [str(cell).strip() for cell in row if cell is not None]
    if not values:
        return False
    return not any(looks_numeric(value) for value in values)


def _detect_header_row(rows: list[tuple[object, ...]]) -> int | None:
    for index, row in enumerate(rows):
        if _is_likely_header_row(row):
            return index + 1
    return None


def _select_worksheet(workbook: Any) -> tuple[str, list[tuple[object, ...]]]:
    """Return the title and all rows of the first visible non-empty worksheet."""
    for worksheet in workbook.worksheets:
        if worksheet.sheet_state != "visible":
            continue
        rows: list[tuple[object, ...]] = list(worksheet.iter_rows(values_only=True))
        if any(any(_has_visible_value(cell) for cell in row) for row in rows):
            return worksheet.title, rows
    raise ValueError("Excel workbook must contain at least one visible non-empty worksheet.")


def read_excel_source(
    local_path: Path,
) -> tuple[ExcelSourceFormat, list[list[str]], list[str], list[list[str]]]:
    """
    Read Excel source settings, raw sample rows, column names, and all data rows.

    The selected sheet is the first visible, non-empty worksheet in workbook order.
    Returns (source_format, sample_rows, column_names, inference_rows).
    """
    workbook = openpyxl.load_workbook(str(local_path), read_only=True, data_only=True)
    try:
        title, all_rows = _select_worksheet(workbook)
    finally:
        workbook.close()

    header_row_index = _detect_header_row(all_rows[:HEADER_SCAN_ROWS])

    col_count = len(all_rows[0]) if all_rows else 0
    if header_row_index is not None:
        header_idx = header_row_index - 1
        if header_idx < len(all_rows):
            column_names = [
                (str(cell).strip() if cell is not None else "") or f"col_{i}"
                for i, cell in enumerate(all_rows[header_idx])
            ]
        else:
            column_names = [f"col_{i}" for i in range(col_count)]
        data_rows = all_rows[header_idx + 1 :]
    else:
        column_names = [f"col_{i}" for i in range(col_count)]
        data_rows = all_rows

    return (
        ExcelSourceFormat(
            sheet_name=title,
            header_mode="present" if header_row_index is not None else "absent",
            header_row_index=header_row_index,
        ),
        [_row_to_strings(row) for row in all_rows[:DISPLAY_RAW_ROWS]],
        column_names,
        [_row_to_strings(row) for row in data_rows],
    )
