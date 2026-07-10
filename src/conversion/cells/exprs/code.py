"""Standardized-code expression builders."""

from __future__ import annotations

from typing import Literal

from shared.db.sql import quote_identifier
from shared.parsing.iso_codes import country_codes, currency_codes, language_codes, sql_in_list

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import parse_code_alias


def _build_code_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    allowed_codes: frozenset[str],
    case: str,
    issue_label: str,
) -> ColumnExprs:
    code_alias = quote_identifier(parse_code_alias(column_name))
    case_fn = "UPPER" if case == "upper" else "LOWER"
    code_expr = f"{case_fn}(TRIM({raw_value}))"
    valid_predicate = f"{code_alias} IN ({sql_in_list(allowed_codes)})"
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {valid_predicate} THEN {code_alias} ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN NOT ({valid_predicate}) THEN '{issue_label}' "
        "ELSE NULL END"
    )
    return ColumnExprs(
        parse_cte_entries=((code_alias, code_expr),),
        normalized_expr=normalized,
        issue_expr=issue,
    )


def build_country_code_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    code_format: Literal["alpha_2", "alpha_3"],
    issue_label: str = "INVALID_COUNTRY_CODE",
) -> ColumnExprs:
    """Build ColumnExprs for an ISO 3166-1 country-code column."""
    return _build_code_exprs(
        column_name,
        nullish_predicate,
        raw_value,
        country_codes(code_format),
        "upper",
        issue_label,
    )


def build_currency_code_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    issue_label: str = "INVALID_CURRENCY_CODE",
) -> ColumnExprs:
    """Build ColumnExprs for an ISO 4217 alpha-3 currency-code column."""
    return _build_code_exprs(
        column_name,
        nullish_predicate,
        raw_value,
        currency_codes(),
        "upper",
        issue_label,
    )


def build_language_code_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    code_format: Literal["alpha_2", "alpha_3"],
    issue_label: str = "INVALID_LANGUAGE_CODE",
) -> ColumnExprs:
    """Build ColumnExprs for an ISO 639 language-code column."""
    return _build_code_exprs(
        column_name,
        nullish_predicate,
        raw_value,
        language_codes(code_format),
        "lower",
        issue_label,
    )
