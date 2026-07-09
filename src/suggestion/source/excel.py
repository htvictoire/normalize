"""Raw Excel loading: workbook access and worksheet selection.

Header-row detection is a heuristic guess, not mechanical loading, and lives
in suggestion.rule_based.source.excel instead — this module only opens the
workbook and picks a worksheet to read from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl


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
