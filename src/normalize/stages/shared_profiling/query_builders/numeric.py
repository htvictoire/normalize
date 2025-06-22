"""Numeric regex and normalization fragments for profile SQL."""

from __future__ import annotations

import re

from normalize.core.numeric_formats import GROUPING_STYLE_INDIAN
from normalize.stages.shared_profiling.sql_helpers import quote_string


def decimal_pattern(
    decimal_separator: str,
    thousand_separator: str,
    *,
    allow_leading_decimal_point: bool,
    grouping_style: str = "western",
) -> str:
    """Build separator-aware decimal regex pattern."""
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


def integer_pattern(thousand_separator: str, *, grouping_style: str = "western") -> str:
    """Build separator-aware integer regex pattern."""
    if not thousand_separator:
        return r"^[+-]?[0-9]+$"
    thousand = re.escape(thousand_separator)
    grouped_integer = _grouped_integer_pattern(thousand, grouping_style=grouping_style)
    return rf"^[+-]?(?:{grouped_integer}|[0-9]+)$"


def normalize_numeric_expr(
    base_value: str,
    decimal_separator: str,
    thousand_separator: str,
) -> str:
    """Normalize decimal/thousand separators into castable numeric text."""
    normalized = base_value
    if thousand_separator:
        normalized = f"REPLACE({normalized}, {quote_string(thousand_separator)}, '')"
    if decimal_separator != ".":
        normalized = f"REPLACE({normalized}, {quote_string(decimal_separator)}, '.')"
    return normalized


def normalize_integer_expr(base_value: str, thousand_separator: str) -> str:
    """Normalize integer grouping separator into castable integer text."""
    if not thousand_separator:
        return base_value
    return f"REPLACE({base_value}, {quote_string(thousand_separator)}, '')"


def _grouped_integer_pattern(thousand: str, *, grouping_style: str) -> str:
    if grouping_style == GROUPING_STYLE_INDIAN:
        # Indian grouping: 12,34,567 or 1,234.
        return rf"[0-9]{{1,3}}(?:{thousand}[0-9]{{2}})*{thousand}[0-9]{{3}}"
    return rf"[0-9]{{1,3}}(?:{thousand}[0-9]{{3}})+"
