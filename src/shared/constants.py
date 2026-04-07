"""Shared cross-package constants."""

from __future__ import annotations

from typing import Final

RAW_INPUT_TABLE_NAME = "raw_input"
EXCEL_SERIAL_DATE_EPOCH_SQL = "DATE '1899-12-30'"

GROUPING_STYLE_WESTERN: Final[str] = "western"
GROUPING_STYLE_INDIAN: Final[str] = "indian"
ALLOWED_GROUPING_STYLES: Final[frozenset[str]] = frozenset(
    {GROUPING_STYLE_WESTERN, GROUPING_STYLE_INDIAN}
)
