"""Currency expression builder."""

from __future__ import annotations

from conversion.stages.cell_normalization.currency_helpers import (
    build_currency_numeric_candidate_expr,
)
from conversion.stages.cell_normalization.naming import parse_cast_alias, parse_match_alias
from conversion.stages.cell_normalization.sql_helpers import quote_identifier, quote_string
from conversion.stages.cell_normalization.transforms.numeric import (
    decimal_pattern_regex,
    normalize_numeric_value,
)


def build_currency_exprs(
    column_name: str,
    nullish_predicate: str,
    *,
    raw_value: str,
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    allow_leading_decimal_point: bool,
) -> tuple[list[tuple[str, str]], str, str]:
    """Build (parse_cte_entries, normalized_expr, issue_expr) for a currency column."""
    trimmed = f"TRIM({raw_value})"
    currency_candidate = build_currency_numeric_candidate_expr(trimmed)
    numeric_value = normalize_numeric_value(
        currency_candidate,
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
    )
    pattern = decimal_pattern_regex(
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    match_expr = f"REGEXP_FULL_MATCH({currency_candidate}, {quote_string(pattern)})"
    cast_expr = f"TRY_CAST({numeric_value} AS DOUBLE)"
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {match_alias} THEN {cast_alias} "
        "ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {match_alias} AND {cast_alias} IS NOT NULL THEN NULL "
        "ELSE 'INVALID_CURRENCY' END"
    )
    return ([(match_alias, match_expr), (cast_alias, cast_expr)], normalized, issue)
