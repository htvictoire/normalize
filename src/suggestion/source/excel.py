"""Excel source helpers for suggestion Stage 1+2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl

from shared.models.operation import ExcelSourceFormat
from suggestion.constants import DISPLAY_RAW_ROWS, HEADER_SCAN_ROWS
from suggestion.source.utils import looks_numeric


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
    return not any(looks_numeric(value) for value in values) and len(set(values)) == len(values)


def _detect_header_row(rows: list[tuple[object, ...]]) -> int | None:
    for index, row in enumerate(rows):
        if _is_likely_header_row(row):
            return index + 1
    return None


def _read_candidate_rows(
    worksheet: Any,
) -> tuple[list[tuple[object, ...]], bool]:
    rows: list[tuple[object, ...]] = []
    has_visible_values = False
    for row in worksheet.iter_rows(values_only=True):
        if len(rows) < DISPLAY_RAW_ROWS:
            rows.append(row)
        if not has_visible_values and any(_has_visible_value(cell) for cell in row):
            has_visible_values = True
        if has_visible_values and len(rows) >= DISPLAY_RAW_ROWS:
            break
    return rows, has_visible_values


def read_excel_source(local_path: Path) -> tuple[ExcelSourceFormat, list[list[str]]]:
    """
    Read Excel source settings and raw sample rows in a single workbook pass.

    The selected sheet is the first visible, non-empty worksheet in workbook order.
    """
    workbook = openpyxl.load_workbook(str(local_path), read_only=True, data_only=True)
    try:
        selected_title: str | None = None
        selected_rows: list[tuple[object, ...]] = []
        for worksheet in workbook.worksheets:
            if worksheet.sheet_state != "visible":
                continue
            candidate_rows, has_visible_values = _read_candidate_rows(worksheet)
            if not has_visible_values:
                continue
            selected_title = worksheet.title
            selected_rows = candidate_rows
            break

        if selected_title is None:
            raise ValueError(
                "Excel workbook must contain at least one visible non-empty worksheet."
            )

        header_row_index = _detect_header_row(selected_rows[:HEADER_SCAN_ROWS])
        return (
            ExcelSourceFormat(
                sheet_name=selected_title,
                header_mode="present" if header_row_index is not None else "absent",
                header_row_index=header_row_index,
            ),
            [_row_to_strings(row) for row in selected_rows[:DISPLAY_RAW_ROWS]],
        )
    finally:
        workbook.close()
