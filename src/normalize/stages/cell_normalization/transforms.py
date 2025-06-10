"""Expression builders for cell normalization SQL."""

from __future__ import annotations

import re
from collections.abc import Sequence

from normalize.stages.cell_normalization.currency_helpers import (
    build_currency_numeric_candidate_expr,
)
from normalize.stages.cell_normalization.sql_helpers import (
    quote_identifier,
    quote_string,
)


def build_column_exprs(
    column_name: str,
    inferred_type: str,
    nullish_predicate: str,
    *,
    true_tokens: Sequence[str],
    false_tokens: Sequence[str],
    decimal_separator: str,
    thousand_separator: str,
    allow_leading_decimal_point: bool,
    date_format: str | None = None,
) -> tuple[str, str]:
    """Build normalized-value and issue-code SQL expressions for one column."""
    quoted_column = quote_identifier(column_name)
    raw_value = f"CAST({quoted_column} AS VARCHAR)"
    normalized_raw_value = f"LOWER(TRIM({raw_value}))"

    if inferred_type == "string":
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {raw_value} END"
        return (normalized, "NULL")
    if inferred_type == "integer":
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL ELSE TRY_CAST({raw_value} AS BIGINT) END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN TRY_CAST({raw_value} AS BIGINT) IS NULL THEN 'INVALID_INTEGER' "
            "ELSE NULL END"
        )
        return (normalized, issue)
    if inferred_type in {"float", "decimal"}:
        trimmed_raw_value = f"TRIM({raw_value})"
        numeric_value = _normalize_numeric_value(
            trimmed_raw_value,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
        )
        decimal_pattern = _decimal_pattern_regex(
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            allow_leading_decimal_point=allow_leading_decimal_point,
        )
        decimal_match = f"REGEXP_FULL_MATCH({trimmed_raw_value}, {quote_string(decimal_pattern)})"
        cast_double = f"TRY_CAST({numeric_value} AS DOUBLE)"
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {decimal_match} THEN {cast_double} "
            "ELSE NULL END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {decimal_match} AND {cast_double} IS NOT NULL THEN NULL "
            "ELSE 'INVALID_DECIMAL' END"
        )
        return (normalized, issue)
    if inferred_type == "currency":
        trimmed_raw_value = f"TRIM({raw_value})"
        currency_candidate = build_currency_numeric_candidate_expr(trimmed_raw_value)
        numeric_value = _normalize_numeric_value(
            currency_candidate,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
        )
        decimal_pattern = _decimal_pattern_regex(
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            allow_leading_decimal_point=allow_leading_decimal_point,
        )
        decimal_match = f"REGEXP_FULL_MATCH({currency_candidate}, {quote_string(decimal_pattern)})"
        cast_double = f"TRY_CAST({numeric_value} AS DOUBLE)"
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {decimal_match} THEN {cast_double} "
            "ELSE NULL END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {decimal_match} AND {cast_double} IS NOT NULL THEN NULL "
            "ELSE 'INVALID_CURRENCY' END"
        )
        return (normalized, issue)
    if inferred_type == "date":
        if date_format is None:
            raise ValueError(f"MISSING_DATE_FORMAT:{column_name}")
        if date_format == "EXCEL_SERIAL":
            parsed_date = f"(DATE '1899-12-30' + TRY_CAST({raw_value} AS INTEGER))"
        else:
            parsed_date = (
                f"TRY_CAST(TRY_STRPTIME({raw_value}, {quote_string(date_format)}) AS DATE)"
            )
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {parsed_date} END"
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {parsed_date} IS NULL THEN 'INVALID_DATE' "
            "ELSE NULL END"
        )
        return (normalized, issue)
    if inferred_type == "boolean":
        true_in_clause = _token_in_clause(true_tokens)
        false_in_clause = _token_in_clause(false_tokens)
        true_match = f"{normalized_raw_value} IN ({true_in_clause})"
        false_match = f"{normalized_raw_value} IN ({false_in_clause})"
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {true_match} THEN TRUE "
            f"WHEN {false_match} THEN FALSE "
            "ELSE NULL END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {true_match} OR {false_match} THEN NULL "
            "ELSE 'INVALID_BOOLEAN' END"
        )
        return (normalized, issue)

    raise ValueError(f"UNSUPPORTED_INFERRED_TYPE:{inferred_type}")


def build_nullish_predicate(column_name: str, null_tokens: Sequence[str]) -> str:
    """Build SQL predicate that matches configured nullish values."""
    quoted_column = quote_identifier(column_name)
    base_value = f"NULLIF(TRIM(CAST({quoted_column} AS VARCHAR)), '')"
    normalized_tokens = sorted(
        {token.strip().lower() for token in null_tokens if token.strip() != ""}
    )
    if not normalized_tokens:
        return f"{base_value} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base_value} IS NULL OR LOWER(TRIM(CAST({quoted_column} AS VARCHAR))) IN ({in_clause})"


def _token_in_clause(tokens: Sequence[str]) -> str:
    if not tokens:
        raise ValueError("EMPTY_BOOLEAN_TOKEN_SET")
    return ", ".join(quote_string(token) for token in tokens)


def _normalize_numeric_value(
    value_expr: str,
    *,
    decimal_separator: str,
    thousand_separator: str,
) -> str:
    normalized = value_expr
    if thousand_separator != "":
        normalized = f"REPLACE({normalized}, {quote_string(thousand_separator)}, '')"
    if decimal_separator != ".":
        normalized = f"REPLACE({normalized}, {quote_string(decimal_separator)}, '.')"
    return normalized


def _decimal_pattern_regex(
    *,
    decimal_separator: str,
    thousand_separator: str,
    allow_leading_decimal_point: bool,
) -> str:
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
