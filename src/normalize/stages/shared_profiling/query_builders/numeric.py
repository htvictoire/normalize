"""Numeric regex and normalization fragments for profile SQL."""

from __future__ import annotations

import re

from normalize.stages.shared_profiling.sql_helpers import quote_string


def decimal_pattern(
    decimal_separator: str,
    thousand_separator: str,
    *,
    allow_leading_decimal_point: bool,
) -> str:
    """Build separator-aware decimal regex pattern."""
    decimal = re.escape(decimal_separator)
    leading_decimal = rf"{decimal}[0-9]+"
    if thousand_separator == "":
        base = rf"[0-9]+(?:{decimal}[0-9]*)?"
        if allow_leading_decimal_point:
            return rf"^[+-]?(?:{base}|{leading_decimal})$"
        return rf"^[+-]?{base}$"
    thousand = re.escape(thousand_separator)
    grouped = rf"(?:[0-9]{{1,3}}(?:{thousand}[0-9]{{3}})+|[0-9]+)(?:{decimal}[0-9]*)?"
    if allow_leading_decimal_point:
        return rf"^[+-]?(?:{grouped}|{leading_decimal})$"
    return rf"^[+-]?{grouped}$"


def integer_pattern(thousand_separator: str) -> str:
    """Build separator-aware integer regex pattern."""
    if thousand_separator == "":
        return r"^[+-]?[0-9]+$"
    thousand = re.escape(thousand_separator)
    return rf"^[+-]?(?:[0-9]{{1,3}}(?:{thousand}[0-9]{{3}})+|[0-9]+)$"


def normalize_numeric_expr(
    base_value: str,
    decimal_separator: str,
    thousand_separator: str,
) -> str:
    """Normalize decimal/thousand separators into castable numeric text."""
    normalized = base_value
    if thousand_separator != "":
        normalized = f"REPLACE({normalized}, {quote_string(thousand_separator)}, '')"
    if decimal_separator != ".":
        normalized = f"REPLACE({normalized}, {quote_string(decimal_separator)}, '.')"
    return normalized


def normalize_integer_expr(base_value: str, thousand_separator: str) -> str:
    """Normalize integer grouping separator into castable integer text."""
    if thousand_separator == "":
        return base_value
    return f"REPLACE({base_value}, {quote_string(thousand_separator)}, '')"
