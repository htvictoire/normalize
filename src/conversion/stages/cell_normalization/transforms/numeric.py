"""Numeric expression builders and regex helpers."""

from __future__ import annotations

import re

from conversion.core.numeric_formats import GROUPING_STYLE_INDIAN
from conversion.stages.cell_normalization.naming import parse_cast_alias, parse_match_alias
from conversion.stages.cell_normalization.sql_helpers import quote_identifier, quote_string


def build_integer_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    thousand_separator: str,
    grouping_style: str,
) -> tuple[list[tuple[str, str]], str, str]:
    """Build (parse_cte_entries, normalized_expr, issue_expr) for an integer column."""
    trimmed = f"TRIM({raw_value})"
    integer_value = _normalize_integer_value(trimmed, thousand_separator=thousand_separator)
    integer_pattern = _integer_pattern_regex(
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
    )
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    match_expr = f"REGEXP_FULL_MATCH({trimmed}, {quote_string(integer_pattern)})"
    cast_expr = f"TRY_CAST({integer_value} AS BIGINT)"
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {match_alias} THEN {cast_alias} "
        "ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {match_alias} AND {cast_alias} IS NOT NULL THEN NULL "
        "ELSE 'INVALID_INTEGER' END"
    )
    return ([(match_alias, match_expr), (cast_alias, cast_expr)], normalized, issue)


def build_decimal_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    allow_leading_decimal_point: bool,
    issue_label: str = "INVALID_DECIMAL",
) -> tuple[list[tuple[str, str]], str, str]:
    """Build (parse_cte_entries, normalized_expr, issue_expr) for a decimal column."""
    trimmed = f"TRIM({raw_value})"
    numeric_value = _normalize_numeric_value(
        trimmed,
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
    )
    decimal_pattern = _decimal_pattern_regex(
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    match_expr = f"REGEXP_FULL_MATCH({trimmed}, {quote_string(decimal_pattern)})"
    cast_expr = f"TRY_CAST({numeric_value} AS DOUBLE)"
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {match_alias} THEN {cast_alias} "
        "ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {match_alias} AND {cast_alias} IS NOT NULL THEN NULL "
        f"ELSE '{issue_label}' END"
    )
    return ([(match_alias, match_expr), (cast_alias, cast_expr)], normalized, issue)


def _normalize_numeric_value(
    value_expr: str,
    decimal_separator: str,
    thousand_separator: str,
) -> str:
    normalized = value_expr
    if thousand_separator:
        normalized = f"REPLACE({normalized}, {quote_string(thousand_separator)}, '')"
    if decimal_separator != ".":
        normalized = f"REPLACE({normalized}, {quote_string(decimal_separator)}, '.')"
    return normalized


def _normalize_integer_value(
    value_expr: str,
    thousand_separator: str,
) -> str:
    if not thousand_separator:
        return value_expr
    return f"REPLACE({value_expr}, {quote_string(thousand_separator)}, '')"


def _decimal_pattern_regex(
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    allow_leading_decimal_point: bool,
) -> str:
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


def _integer_pattern_regex(
    thousand_separator: str,
    grouping_style: str,
) -> str:
    if not thousand_separator:
        return r"^[+-]?[0-9]+$"
    thousand = re.escape(thousand_separator)
    grouped_integer = _grouped_integer_pattern(thousand, grouping_style=grouping_style)
    return rf"^[+-]?(?:{grouped_integer}|[0-9]+)$"


def _grouped_integer_pattern(thousand: str, grouping_style: str) -> str:
    if grouping_style == GROUPING_STYLE_INDIAN:
        return rf"[0-9]{{1,3}}(?:{thousand}[0-9]{{2}})*{thousand}[0-9]{{3}}"
    return rf"[0-9]{{1,3}}(?:{thousand}[0-9]{{3}})+"


# expose helpers for profiling and currency modules
normalize_numeric_value = _normalize_numeric_value
decimal_pattern_regex = _decimal_pattern_regex
integer_pattern_regex = _integer_pattern_regex
