"""AI-only column expression builders.

These configs are AI-suggestable only when extended_type_detection=true, but once
confirmed they execute deterministically like every other ColumnConfig.
"""

from __future__ import annotations

from shared.db.sql import quote_identifier, quote_string
from shared.parsing.structured_strings import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    URL_PATTERN,
    ip_address_pattern,
    lowercase_email_expr,
    phone_e164_candidate_expr,
    regex_full_match_expr,
    trim_cast_expr,
)

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import parse_categorical_alias, parse_structured_alias


def _map_case_expr(value_alias: str, value_map: dict[str, str]) -> str:
    cases = [
        f"WHEN {value_alias} = {quote_string(raw)} THEN {quote_string(canonical)}"
        for raw, canonical in sorted(value_map.items())
    ]
    if not cases:
        return value_alias
    return "CASE " + " ".join(cases) + f" ELSE {value_alias} END"


def build_categorical_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    value_map: dict[str, str],
    unknown_value_policy: str,
    issue_label: str = "INVALID_CATEGORICAL",
) -> ColumnExprs:
    """Build ColumnExprs for a confirmed categorical mapping."""
    value_alias = quote_identifier(parse_categorical_alias(column_name))
    mapped_expr = _map_case_expr(value_alias, value_map)
    known_predicate = f"{value_alias} IN ({', '.join(quote_string(v) for v in sorted(value_map))})"
    if not value_map:
        known_predicate = "FALSE"

    unknown_expr = "NULL" if unknown_value_policy == "issue_and_null" else value_alias
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {known_predicate} THEN {mapped_expr} "
        f"ELSE {unknown_expr} END"
    )
    if unknown_value_policy == "keep":
        issue = "NULL"
    else:
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN NOT ({known_predicate}) THEN '{issue_label}' "
            "ELSE NULL END"
        )
    return ColumnExprs(
        parse_cte_entries=((value_alias, f"TRIM({raw_value})"),),
        normalized_expr=normalized,
        issue_expr=issue,
    )


def _build_regex_string_exprs(
    column_name: str,
    nullish_predicate: str,
    normalized_expr: str,
    pattern: str,
    issue_label: str,
) -> ColumnExprs:
    alias = quote_identifier(parse_structured_alias(column_name))
    valid = regex_full_match_expr(alias, pattern)
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {valid} THEN {alias} ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN NOT ({valid}) THEN '{issue_label}' "
        "ELSE NULL END"
    )
    return ColumnExprs(
        parse_cte_entries=((alias, normalized_expr),),
        normalized_expr=normalized,
        issue_expr=issue,
    )


def build_email_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    issue_label: str = "INVALID_EMAIL",
) -> ColumnExprs:
    """Build ColumnExprs for an email-address column."""
    return _build_regex_string_exprs(
        column_name,
        nullish_predicate,
        lowercase_email_expr(raw_value),
        EMAIL_PATTERN,
        issue_label,
    )


def build_url_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    issue_label: str = "INVALID_URL",
) -> ColumnExprs:
    """Build ColumnExprs for a URL column."""
    return _build_regex_string_exprs(
        column_name,
        nullish_predicate,
        trim_cast_expr(raw_value),
        URL_PATTERN,
        issue_label,
    )


def build_ip_address_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    version: str,
    issue_label: str = "INVALID_IP_ADDRESS",
) -> ColumnExprs:
    """Build ColumnExprs for an IP-address column."""
    return _build_regex_string_exprs(
        column_name,
        nullish_predicate,
        trim_cast_expr(raw_value),
        ip_address_pattern(version),
        issue_label,
    )


def build_phone_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    issue_label: str = "INVALID_PHONE",
) -> ColumnExprs:
    """Build ColumnExprs for a phone column normalized to a conservative E.164-like form."""
    return _build_regex_string_exprs(
        column_name,
        nullish_predicate,
        phone_e164_candidate_expr(raw_value),
        PHONE_PATTERN,
        issue_label,
    )
