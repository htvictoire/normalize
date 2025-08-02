"""Type dispatcher for cell normalization SQL expressions."""

from __future__ import annotations

from collections.abc import Sequence

from normalize.stages.cell_normalization.transforms.boolean import build_boolean_exprs
from normalize.stages.cell_normalization.transforms.currency import build_currency_exprs
from normalize.stages.cell_normalization.transforms.date import build_date_exprs
from normalize.stages.cell_normalization.transforms.numeric import (
    build_decimal_exprs,
    build_integer_exprs,
)


def build_column_exprs(
    column_name: str,
    inferred_type: str,
    nullish_predicate: str,
    *,
    raw_value: str,
    normalized_raw_value: str,
    true_tokens: Sequence[str],
    false_tokens: Sequence[str],
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    allow_leading_decimal_point: bool,
    date_format: str | None = None,
) -> tuple[list[tuple[str, str]], str, str]:
    """Route to the appropriate type-specific expression builder.

    Returns (parse_cte_entries, normalized_expr, issue_expr).
    """
    if inferred_type == "string":
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {raw_value} END"
        return ([], normalized, "NULL")

    if inferred_type == "integer":
        return build_integer_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
        )

    if inferred_type in {"float", "decimal"}:
        return build_decimal_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
            allow_leading_decimal_point=allow_leading_decimal_point,
        )

    if inferred_type == "currency":
        return build_currency_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
            allow_leading_decimal_point=allow_leading_decimal_point,
        )

    if inferred_type == "date":
        return build_date_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            date_format=date_format,
        )

    if inferred_type == "boolean":
        return build_boolean_exprs(
            nullish_predicate,
            normalized_raw_value,
            true_tokens=true_tokens,
            false_tokens=false_tokens,
        )

    raise ValueError(f"UNSUPPORTED_INFERRED_TYPE:{inferred_type}")
