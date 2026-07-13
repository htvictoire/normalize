"""Numeric expression builders."""

from __future__ import annotations

from shared.constants import DECIMAL_INT64_MAX_PRECISION, DECIMAL_MAX_PRECISION
from shared.db.sql import quote_identifier, quote_string
from shared.models.profiling import MixedNumberFormatProfile
from shared.parsing.numeric import (
    decimal_normalize_sql,
    decimal_pattern_regex,
    has_significant_digit_sql,
    integer_normalize_sql,
    integer_pattern_regex,
    strip_group_only_sql,
)

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import (
    parse_cast_alias,
    parse_clean_alias,
    parse_match_alias,
    parse_norm_alias,
)


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


def _decimal_column_type(profile: MixedNumberFormatProfile) -> str:
    """Return the DECIMAL type a decimal column is stored as.

    The scale is the column's own, so no value is rounded that DuckDB could have held.
    It decides the stored size — ``3.96`` at scale 2 is the integer 396, at scale 18 it
    is 3960000000000000000 — so a column pays only for the fraction it carries.

    The precision is not taken from the data, so that a larger value in a later run
    cannot change the artifact's schema under its consumers. It widens only when the
    column no longer fits an int64.
    """
    scale = profile.max_scale
    integer_digits = profile.max_integer_digits
    precision = (
        DECIMAL_INT64_MAX_PRECISION
        if integer_digits + scale <= DECIMAL_INT64_MAX_PRECISION
        else DECIMAL_MAX_PRECISION
    )
    # Past 38 digits the two cannot both fit and the integer digits are kept: a value too
    # large for the precision is reported by the cast, where a fraction too long is
    # silently rounded.
    scale = max(min(scale, precision - integer_digits), 0)
    return f"DECIMAL({precision}, {scale})"


def build_decimal_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    profile: MixedNumberFormatProfile,
    issue_label: str = "INVALID_DECIMAL",
) -> ColumnExprs:
    """Build ColumnExprs for a decimal column.

    The locale is resolved per value, so a column mixing ``1,234.56`` with
    ``1.234,56`` normalizes both instead of nulling whichever one lost the
    column-wide separator vote.

    A value below the stored type's smallest magnitude rounds to exactly zero, which
    destroys it rather than trimming it. Such a cell is reported instead of stored.
    """
    decimal_type = _decimal_column_type(profile)
    decimal_pattern = decimal_pattern_regex()
    clean_alias = quote_identifier(parse_clean_alias(column_name))
    norm_alias = quote_identifier(parse_norm_alias(column_name))
    match_alias = quote_identifier(parse_match_alias(column_name))
    cast_alias = quote_identifier(parse_cast_alias(column_name))
    return _build_numeric_exprs(
        nullish_predicate=nullish_predicate,
        match_alias=match_alias,
        cast_alias=cast_alias,
        extra_cte_entries=(
            (clean_alias, strip_group_only_sql(raw_value)),
            (norm_alias, decimal_normalize_sql(clean_alias)),
        ),
        match_expr=f"REGEXP_FULL_MATCH({clean_alias}, {quote_string(decimal_pattern)})",
        cast_expr=f"TRY_CAST({norm_alias} AS {decimal_type})",
        extra_valid_predicate=(
            f"NOT ({cast_alias} = 0 AND {has_significant_digit_sql(norm_alias)})"
        ),
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
    extra_valid_predicate: str | None = None,
) -> ColumnExprs:
    """Assemble the normalized/issue pair for a numeric column.

    The two expressions are complements by construction: a cell yields a value or an
    issue code, never both and never neither. Quality metrics read an output NULL as a
    defect only when _parse_issues holds a code for it, so a cell nulled without a code
    would be miscounted as a value the source never had.

    ``extra_valid_predicate`` narrows what counts as parsed beyond casting cleanly.
    """
    valid = f"{match_alias} AND {cast_alias} IS NOT NULL"
    if extra_valid_predicate is not None:
        valid = f"{valid} AND {extra_valid_predicate}"
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {valid} THEN {cast_alias} "
        "ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {valid} THEN NULL "
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
