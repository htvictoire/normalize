"""Heuristic Excel header-row detection and inference-row assembly.

Header-row detection here is a guess, not mechanical loading — mechanical
workbook/worksheet access lives in suggestion.source.excel.
"""

from __future__ import annotations

from pathlib import Path

from shared.models.operation import ExcelSourceFormat

from suggestion.constants import DISPLAY_RAW_ROWS
from suggestion.rule_based.constants import HEADER_SCAN_ROWS
from suggestion.rule_based.source.heuristics import looks_numeric
from suggestion.source.excel import read_excel_raw_rows, row_to_strings


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


def read_excel_source(
    local_path: Path,
) -> tuple[ExcelSourceFormat, list[list[str]], list[str], list[list[str]]]:
    """
    Read Excel source settings, raw sample rows, column names, and all data rows.

    The selected sheet is the first visible, non-empty worksheet in workbook order.
    Returns (source_format, sample_rows, column_names, inference_rows).
    """
    title, all_rows = read_excel_raw_rows(local_path)

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
        [row_to_strings(row) for row in all_rows[:DISPLAY_RAW_ROWS]],
        column_names,
        [row_to_strings(row) for row in data_rows],
    )
