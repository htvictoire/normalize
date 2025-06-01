"""SQL query construction for shared one-pass profiling."""

from __future__ import annotations

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
) -> str:
    """Build one-pass aggregate SQL query for profiling all columns."""
    source_exprs: list[str] = []
    exprs: list[str] = ["COUNT(*) AS row_count"]
    null_in_clause = _token_in_clause(token_policy.null_tokens)
    boolean_in_clause = _token_in_clause(token_policy.boolean_tokens)

    for index, column_name in enumerate(columns):
        quoted = quote_identifier(column_name)
        base_alias = f"__c{index}_base"
        lower_alias = f"__c{index}_lower"
        double_alias = f"__c{index}_double"
        source_exprs.append(f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') AS {base_alias}")
        source_exprs.append(f"LOWER(TRIM(CAST({quoted} AS VARCHAR))) AS {lower_alias}")
        source_exprs.append(f"TRY_CAST({quoted} AS DOUBLE) AS {double_alias}")

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
            f"WHEN REGEXP_FULL_MATCH({base_value}, '^[+-]?[0-9]+$') THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__int_match_count"
        )
        exprs.append(
            "SUM(CASE "
            f"WHEN {base_value} IS NULL THEN 0 "
            f"WHEN {double_alias} IS NOT NULL THEN 1 "
            "ELSE 0 END) "
            f"AS {column_name}__float_match_count"
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
