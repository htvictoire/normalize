"""Numeric expression builders."""

from __future__ import annotations

from shared.db.sql import quote_identifier, quote_string
from shared.parsing.numeric import (
    decimal_normalize_sql,
    decimal_pattern_regex,
    integer_normalize_sql,
    integer_pattern_regex,
    strip_group_only_sql,
)

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import parse_cast_alias, parse_clean_alias, parse_match_alias


def build_integer_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    issue_label: str = "INVALID_INTEGER",
) -> ColumnExprs:
    """Build ColumnExprs for an integer column."""
    clean_alias = quote_identifier(parse_clean_alias(column_name))
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    return _build_numeric_exprs(
        nullish_predicate=nullish_predicate,
        match_alias=match_alias,
        cast_alias=cast_alias,
        extra_cte_entries=((clean_alias, strip_group_only_sql(raw_value)),),
        match_expr=(
            f"REGEXP_FULL_MATCH({clean_alias}, {quote_string(integer_pattern_regex())})"
        ),
        cast_expr=f"TRY_CAST({integer_normalize_sql(clean_alias)} AS BIGINT)",
        issue_label=issue_label,
    )


def build_decimal_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    allow_leading_decimal_point: bool,
    issue_label: str = "INVALID_DECIMAL",
) -> ColumnExprs:
    """Build ColumnExprs for a decimal column.

    The locale is resolved per value, so a column mixing ``1,234.56`` with
    ``1.234,56`` normalizes both instead of nulling whichever one lost the
    column-wide separator vote.
    """
    decimal_pattern = decimal_pattern_regex(
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    clean_alias = quote_identifier(parse_clean_alias(column_name))
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    return _build_numeric_exprs(
        nullish_predicate=nullish_predicate,
        match_alias=match_alias,
        cast_alias=cast_alias,
        extra_cte_entries=((clean_alias, strip_group_only_sql(raw_value)),),
        match_expr=f"REGEXP_FULL_MATCH({clean_alias}, {quote_string(decimal_pattern)})",
        cast_expr=f"TRY_CAST({decimal_normalize_sql(clean_alias)} AS DOUBLE)",
        issue_label=issue_label,
    )


def _build_numeric_exprs(
    *,
    nullish_predicate: str,
    match_alias: str,
    cast_alias: str,
    extra_cte_entries: tuple[tuple[str, str], ...],
    match_expr: str,
    cast_expr: str,
    issue_label: str,
) -> ColumnExprs:
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
        # The cleaned value is materialised first so the match and cast below
        # reference it by alias instead of re-deriving it.
        parse_cte_entries=(
            *extra_cte_entries,
            (match_alias, match_expr),
            (cast_alias, cast_expr),
        ),
        normalized_expr=normalized,
        issue_expr=issue,
    )
