"""Numeric expression builders."""

from __future__ import annotations

from shared.db.sql import quote_identifier, quote_string
from shared.parsing.numeric import decimal_pattern_regex, integer_pattern_regex

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import parse_cast_alias, parse_match_alias


def build_integer_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    thousand_separator: str,
    grouping_style: str,
    issue_label: str = "INVALID_INTEGER",
) -> ColumnExprs:
    """Build ColumnExprs for an integer column."""
    integer_value = _normalize_integer_value(raw_value, thousand_separator=thousand_separator)
    integer_pattern = integer_pattern_regex(
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
    )
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    match_expr = f"REGEXP_FULL_MATCH({raw_value}, {quote_string(integer_pattern)})"
    cast_expr = f"TRY_CAST({integer_value} AS BIGINT)"
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
    return ColumnExprs(
        parse_cte_entries=((match_alias, match_expr), (cast_alias, cast_expr)),
        normalized_expr=normalized,
        issue_expr=issue,
    )


def build_decimal_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    allow_leading_decimal_point: bool,
    issue_label: str = "INVALID_DECIMAL",
) -> ColumnExprs:
    """Build ColumnExprs for a decimal column."""
    numeric_value = _normalize_numeric_value(
        raw_value,
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
    )
    decimal_pattern = decimal_pattern_regex(
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    match_expr = f"REGEXP_FULL_MATCH({raw_value}, {quote_string(decimal_pattern)})"
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
    return ColumnExprs(
        parse_cte_entries=((match_alias, match_expr), (cast_alias, cast_expr)),
        normalized_expr=normalized,
        issue_expr=issue,
    )


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
