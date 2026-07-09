"""Heuristic Excel header-row detection and inference-row assembly.

Header-row detection here is a guess, not mechanical loading — mechanical
workbook/worksheet access lives in suggestion.source.excel.
"""

from __future__ import annotations

from pathlib import Path

from shared.models.operation import ExcelSourceFormat, HeaderMode

from suggestion.rule_based.constants import HEADER_SCAN_ROWS
from suggestion.rule_based.source.heuristics import looks_numeric
from suggestion.source.excel import assemble_excel_reading, read_excel_raw_rows


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
    The header row is detected heuristically; slicing is mechanical (shared).
    Returns (source_format, sample_rows, column_names, inference_rows).
    """
    title, all_rows = read_excel_raw_rows(local_path)
    header_row_index = _detect_header_row(all_rows[:HEADER_SCAN_ROWS])
    header_mode: HeaderMode = "present" if header_row_index is not None else "absent"
    return assemble_excel_reading(title, all_rows, header_mode, header_row_index)
