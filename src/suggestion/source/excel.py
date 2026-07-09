"""Raw Excel loading: workbook access, worksheet selection, and row assembly.

Header-row *detection* is a heuristic guess and lives per-strategy (rule-based
uses numeric density; the AI path asks the model). This module only does the
mechanical parts: opening the workbook, picking a worksheet, and — given a
header decision — slicing rows into a resolved reading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl

from shared.models.operation import ExcelSourceFormat, HeaderMode

from suggestion.constants import DISPLAY_RAW_ROWS


def _has_visible_value(cell: object) -> bool:
    if cell is None:
        return False
    return bool(str(cell).strip())


def row_to_strings(row: tuple[object, ...]) -> list[str]:
    return [str(cell) if cell is not None else "" for cell in row]


def _select_worksheet(workbook: Any) -> tuple[str, list[tuple[object, ...]]]:
    """Return the title and all rows of the first visible non-empty worksheet."""
    for worksheet in workbook.worksheets:
        if worksheet.sheet_state != "visible":
            continue
        rows: list[tuple[object, ...]] = list(worksheet.iter_rows(values_only=True))
        if any(any(_has_visible_value(cell) for cell in row) for row in rows):
            return worksheet.title, rows
    raise ValueError("Excel workbook must contain at least one visible non-empty worksheet.")


def read_excel_raw_rows(local_path: Path) -> tuple[str, list[tuple[object, ...]]]:
    """Open the workbook and return (sheet_name, all_rows) for the selected worksheet."""
    workbook = openpyxl.load_workbook(str(local_path), read_only=True, data_only=True)
    try:
        return _select_worksheet(workbook)
    finally:
        workbook.close()


def assemble_excel_reading(
    sheet_name: str,
    all_rows: list[tuple[object, ...]],
    header_mode: HeaderMode,
    header_row_index: int | None,
) -> tuple[ExcelSourceFormat, list[list[str]], list[str], list[list[str]]]:
    """Slice loaded rows into (source_format, sample_rows, column_names, inference_rows).

    Mechanical given a header decision — the decision itself (present/absent and
    which row) is made per-strategy and passed in.
    """
    col_count = len(all_rows[0]) if all_rows else 0
    if header_mode == "present" and header_row_index is not None:
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
            sheet_name=sheet_name,
            header_mode=header_mode,
            header_row_index=header_row_index,
        ),
        [row_to_strings(row) for row in all_rows[:DISPLAY_RAW_ROWS]],
        column_names,
        [row_to_strings(row) for row in data_rows],
    )
