"""SQL query construction for shared one-pass profiling."""

from __future__ import annotations

from normalize.core.token_policy import TokenPolicy
from normalize.stages.shared_profiling.query_builders.currency import (
    accounting_negative_predicate,
    apply_accounting_sign_expr,
    currency_marker_predicate,
    strip_currency_affix_expr,
)
from normalize.stages.shared_profiling.query_builders.numeric import (
    decimal_pattern,
    integer_pattern,
    normalize_integer_expr,
    normalize_numeric_expr,
)
from normalize.stages.shared_profiling.query_builders.predicates import (
    has_any_separator_predicate,
    swapped_float_predicate,
)
from normalize.stages.shared_profiling.query_builders.tokens import token_in_clause
from normalize.stages.shared_profiling.sql_helpers import quote_identifier, quote_string


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
    null_in_clause = token_in_clause(token_policy.null_tokens)
    boolean_in_clause = token_in_clause(token_policy.boolean_tokens)
    decimal = decimal_pattern(
        decimal_separator,
        thousand_separator,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )
    integer = integer_pattern(thousand_separator)
    normalized_separator_predicate = has_any_separator_predicate(
        "BASE_VALUE_PLACEHOLDER",
        [decimal_separator, thousand_separator],
    )
    has_separator_template = normalized_separator_predicate
    swapped_float_template = "FALSE"
    if thousand_separator:
        swapped_pattern = decimal_pattern(
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
        currency_symbol_stripped_alias = f"__c{index}_currency_symbol_stripped"
        currency_signed_alias = f"__c{index}_currency_signed"
        normalized_currency_alias = f"__c{index}_normalized_currency"

        source_exprs.append(f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') AS {base_alias}")
        source_exprs.append(f"LOWER(TRIM(CAST({quoted} AS VARCHAR))) AS {lower_alias}")
        source_exprs.append(
            f"{normalize_numeric_expr(base_alias, decimal_separator, thousand_separator)} "
            f"AS {normalized_alias}"
        )
        source_exprs.append(
            f"{normalize_integer_expr(base_alias, thousand_separator)} AS {normalized_int_alias}"
        )
        if thousand_separator:
            source_exprs.append(
                f"{normalize_numeric_expr(base_alias, thousand_separator, decimal_separator)} "
                f"AS {normalized_swapped_alias}"
            )
        else:
            source_exprs.append(f"NULL AS {normalized_swapped_alias}")

        marker_predicate = currency_marker_predicate(lower_alias)
        source_exprs.append(
            "CASE "
            f"WHEN {marker_predicate} THEN {strip_currency_affix_expr(lower_alias)} "
            "ELSE NULL END "
            f"AS {currency_symbol_stripped_alias}"
        )
        source_exprs.append(
            "CASE "
            f"WHEN {marker_predicate} "
            f"THEN {apply_accounting_sign_expr(currency_symbol_stripped_alias)} "
            "ELSE NULL END "
            f"AS {currency_signed_alias}"
        )
        normalized_currency_expr = normalize_numeric_expr(
            currency_signed_alias,
            decimal_separator,
            thousand_separator,
        )
        source_exprs.append(f"{normalized_currency_expr} AS {normalized_currency_alias}")

        base_value = base_alias
        decimal_match_predicate = (
            f"REGEXP_FULL_MATCH({base_value}, {quote_string(decimal)}) "
            f"AND TRY_CAST({normalized_alias} AS DOUBLE) IS NOT NULL"
        )
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
            f"WHEN REGEXP_FULL_MATCH({base_value}, {quote_string(integer)}) "
            f"AND TRY_CAST({normalized_int_alias} AS BIGINT) IS NOT NULL THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__int_match_count"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {decimal_match_predicate} THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__float_match_count"
        )
        swapped_predicate = swapped_float_predicate(
            swapped_float_template,
            base_value,
            normalized_swapped_alias,
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {swapped_predicate} THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__swapped_float_match_count"
        )

        currency_value_match_predicate = (
            f"REGEXP_FULL_MATCH({currency_signed_alias}, {quote_string(decimal)}) "
            f"AND TRY_CAST({normalized_currency_alias} AS DOUBLE) IS NOT NULL"
        )
        currency_match_predicate = (
            f"{decimal_match_predicate} "
            f"OR (({marker_predicate}) AND {currency_value_match_predicate})"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {currency_match_predicate} THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__currency_match_count"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {accounting_negative_predicate(currency_symbol_stripped_alias)} THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__accounting_negative_match_count"
        )

        nullish_predicate = (
            f"{base_value} IS NULL"
            if null_in_clause is None
            else f"{base_value} IS NULL OR {lower_alias} IN ({null_in_clause})"
        )
        exprs.append(
            f"SUM(CASE WHEN {nullish_predicate} THEN 1 ELSE 0 END) "
            f"AS {column_name}__nullish_count"
        )

    return (
        "WITH profile_source AS ("
        f"SELECT {', '.join(source_exprs)} FROM {table_name}"
        ") "
        f"SELECT {', '.join(exprs)} FROM profile_source"
    )
