"""Regex pattern builders for numeric format matching."""

from __future__ import annotations

import re

from shared.constants import GROUPING_STYLE_INDIAN


def decimal_pattern_regex(
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    allow_leading_decimal_point: bool,
) -> str:
    """Return a regex pattern that matches valid decimal-formatted strings."""
    decimal = re.escape(decimal_separator)
    leading_decimal = rf"{decimal}[0-9]+"
    if not thousand_separator:
        base = rf"[0-9]+(?:{decimal}[0-9]*)?"
        if allow_leading_decimal_point:
            return rf"^[+-]?(?:{base}|{leading_decimal})$"
        return rf"^[+-]?{base}$"
    thousand = re.escape(thousand_separator)
    grouped_integer = _grouped_integer_pattern(thousand, grouping_style=grouping_style)
    grouped = rf"(?:{grouped_integer}|[0-9]+)(?:{decimal}[0-9]*)?"
    if allow_leading_decimal_point:
        return rf"^[+-]?(?:{grouped}|{leading_decimal})$"
    return rf"^[+-]?{grouped}$"


def integer_pattern_regex(
    thousand_separator: str,
    grouping_style: str,
) -> str:
    """Return a regex pattern that matches valid integer-formatted strings."""
    if not thousand_separator:
        return r"^[+-]?[0-9]+$"
    thousand = re.escape(thousand_separator)
    grouped_integer = _grouped_integer_pattern(thousand, grouping_style=grouping_style)
    return rf"^[+-]?(?:{grouped_integer}|[0-9]+)$"


def _grouped_integer_pattern(thousand: str, grouping_style: str) -> str:
    if grouping_style == GROUPING_STYLE_INDIAN:
        return rf"[0-9]{{1,3}}(?:{thousand}[0-9]{{2}})*{thousand}[0-9]{{3}}"
    return rf"[0-9]{{1,3}}(?:{thousand}[0-9]{{3}})+"
