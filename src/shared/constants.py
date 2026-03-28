"""Shared cross-package constants."""

from __future__ import annotations

from typing import Final

RAW_INPUT_TABLE_NAME = "raw_input"

GROUPING_STYLE_WESTERN: Final[str] = "western"
GROUPING_STYLE_INDIAN: Final[str] = "indian"
ALLOWED_GROUPING_STYLES: Final[frozenset[str]] = frozenset(
    {GROUPING_STYLE_WESTERN, GROUPING_STYLE_INDIAN}
)
