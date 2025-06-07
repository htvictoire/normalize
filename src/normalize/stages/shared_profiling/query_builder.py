"""SQL query construction for shared one-pass profiling."""

from __future__ import annotations

import re
from collections.abc import Sequence

from normalize.core.token_policy import TokenPolicy
from normalize.stages.shared_profiling.sql_helpers import (
    quote_identifier,
    quote_string,
)


def build_profile_query(
    columns: list[str],
    *,
    table_name: str,
    token_policy: TokenPolicy,
    decimal_separator: str,
    thousand_separator: str,
    allow_leading_decimal_point: bool,
) -> str:
    """Build one-pass aggregate SQL query for profiling all columns."""
    source_exprs: list[str] = []
    exprs: list[str] = ["COUNT(*) AS row_count"]
    null_in_clause = _token_in_clause(token_policy.null_tokens)
    boolean_in_clause = _token_in_clause(token_policy.boolean_tokens)
    decimal_pattern = _decimal_pattern(
        decimal_separator,
        thousand_separator,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    integer_pattern = _integer_pattern(thousand_separator)
    normalized_separator_predicate = _has_any_separator_predicate(
        "BASE_VALUE_PLACEHOLDER",
        [decimal_separator, thousand_separator],
    )
    has_separator_template = normalized_separator_predicate
    swapped_float_template = "FALSE"
    if thousand_separator != "":
        swapped_pattern = _decimal_pattern(
            thousand_separator,
            decimal_separator,
            allow_leading_decimal_point=allow_leading_decimal_point,
        )
        swapped_float_template = (
            f"{has_separator_template} "
            f"AND REGEXP_FULL_MATCH(BASE_VALUE_PLACEHOLDER, {quote_string(swapped_pattern)}) "
            "AND TRY_CAST(SWAPPED_VALUE_PLACEHOLDER AS DOUBLE) IS NOT NULL"
        )

    for index, column_name in enumerate(columns):
        quoted = quote_identifier(column_name)
        base_alias = f"__c{index}_base"
        lower_alias = f"__c{index}_lower"
        normalized_alias = f"__c{index}_normalized"
        normalized_int_alias = f"__c{index}_normalized_int"
        normalized_swapped_alias = f"__c{index}_normalized_swapped"
        source_exprs.append(f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') AS {base_alias}")
        source_exprs.append(f"LOWER(TRIM(CAST({quoted} AS VARCHAR))) AS {lower_alias}")
        source_exprs.append(
            f"{_normalize_numeric_expr(base_alias, decimal_separator, thousand_separator)} "
            f"AS {normalized_alias}"
        )
        source_exprs.append(
            f"{_normalize_integer_expr(base_alias, thousand_separator)} AS {normalized_int_alias}"
        )
        if thousand_separator != "":
            source_exprs.append(
                f"{_normalize_numeric_expr(base_alias, thousand_separator, decimal_separator)} "
                f"AS {normalized_swapped_alias}"
            )
        else:
            source_exprs.append(f"NULL AS {normalized_swapped_alias}")

        base_value = base_alias
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            "ELSE 1 END) "
            f"AS {column_name}__non_empty_count"
        )
        bool_match_predicate = (
            "FALSE" if boolean_in_clause is None else f"{lower_alias} IN ({boolean_in_clause})"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {bool_match_predicate} THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__bool_match_count"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN REGEXP_FULL_MATCH({base_value}, {quote_string(integer_pattern)}) "
            f"AND TRY_CAST({normalized_int_alias} AS BIGINT) IS NOT NULL THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__int_match_count"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN REGEXP_FULL_MATCH({base_value}, {quote_string(decimal_pattern)}) "
            f"AND TRY_CAST({normalized_alias} AS DOUBLE) IS NOT NULL THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__float_match_count"
        )
        swapped_predicate = _swapped_float_predicate(
            swapped_float_template, base_value, normalized_swapped_alias
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {swapped_predicate} THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__swapped_float_match_count"
        )
        nullish_predicate = (
            f"{base_value} IS NULL"
            if null_in_clause is None
            else f"{base_value} IS NULL OR {lower_alias} IN ({null_in_clause})"
        )
        exprs.append(
            f"SUM(CASE WHEN {nullish_predicate} THEN 1 ELSE 0 END) AS {column_name}__nullish_count"
        )

    return (
        "WITH profile_source AS ("
        f"SELECT {', '.join(source_exprs)} FROM {table_name}"
        ") "
        f"SELECT {', '.join(exprs)} FROM profile_source"
    )


def _token_in_clause(tokens: Sequence[str]) -> str | None:
    if not tokens:
        return None
    return ", ".join(quote_string(token) for token in tokens)


def _decimal_pattern(
    decimal_separator: str,
    thousand_separator: str,
    *,
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


def _integer_pattern(thousand_separator: str) -> str:
    if thousand_separator == "":
        return r"^[+-]?[0-9]+$"
    thousand = re.escape(thousand_separator)
    return rf"^[+-]?(?:[0-9]{{1,3}}(?:{thousand}[0-9]{{3}})+|[0-9]+)$"


def _normalize_numeric_expr(
    base_value: str,
    decimal_separator: str,
    thousand_separator: str,
) -> str:
    normalized = base_value
    if thousand_separator != "":
        normalized = f"REPLACE({normalized}, {quote_string(thousand_separator)}, '')"
    if decimal_separator != ".":
        normalized = f"REPLACE({normalized}, {quote_string(decimal_separator)}, '.')"
    return normalized


def _normalize_integer_expr(base_value: str, thousand_separator: str) -> str:
    if thousand_separator == "":
        return base_value
    return f"REPLACE({base_value}, {quote_string(thousand_separator)}, '')"


def _has_any_separator_predicate(base_value: str, separators: Sequence[str]) -> str:
    unique_separators = sorted({separator for separator in separators if separator != ""})
    if not unique_separators:
        return "FALSE"
    return " OR ".join(
        f"STRPOS({base_value}, {quote_string(separator)}) > 0"
        for separator in unique_separators
    )


def _swapped_float_predicate(
    swapped_float_template: str,
    base_value: str,
    normalized_swapped_alias: str,
) -> str:
    return (
        swapped_float_template.replace("BASE_VALUE_PLACEHOLDER", base_value)
        .replace("SWAPPED_VALUE_PLACEHOLDER", normalized_swapped_alias)
    )
