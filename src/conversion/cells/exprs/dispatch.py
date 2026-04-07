"""Type dispatcher for cell normalization SQL expressions."""

from __future__ import annotations

from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    DateColumnConfig,
    DecimalSyntaxColumnConfig,
    IntegerColumnConfig,
    StringColumnConfig,
)
from shared.parsing.normalizer import build_value_candidate_expr

from conversion.cells.exprs.boolean import build_boolean_exprs
from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.exprs.date import build_date_exprs
from conversion.cells.exprs.numeric import (
    build_decimal_exprs,
    build_integer_exprs,
)


def build_column_exprs(
    column_name: str,
    config: ColumnConfig,
    nullish_predicate: str,
    raw_value: str,
    normalized_raw_value: str,
) -> ColumnExprs:
    """Route to the appropriate type-specific expression builder."""
    if isinstance(config, StringColumnConfig):
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {raw_value} END"
        return ColumnExprs(parse_cte_entries=(), normalized_expr=normalized, issue_expr="NULL")

    issue_label = f"INVALID_{config.type.upper()}"

    if isinstance(config, BooleanColumnConfig):
        return build_boolean_exprs(
            nullish_predicate,
            normalized_raw_value,
            true_tokens=config.true_tokens,
            false_tokens=config.false_tokens,
            issue_label=issue_label,
        )

    if isinstance(config, DateColumnConfig):
        return build_date_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            date_format=config.date_format,
            issue_label=issue_label,
        )

    if isinstance(config, IntegerColumnConfig):
        return build_integer_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            thousand_separator=config.thousand_separator,
            grouping_style=config.grouping_style,
            issue_label=issue_label,
        )

    # Decimal-syntax types: preprocess via the shared normalizer, then build decimal exprs.
    candidate = build_value_candidate_expr(raw_value, config)

    if isinstance(config, DecimalSyntaxColumnConfig):
        return build_decimal_exprs(
            column_name,
            nullish_predicate,
            raw_value=candidate,
            decimal_separator=config.decimal_separator,
            thousand_separator=config.thousand_separator,
            grouping_style=config.grouping_style,
            allow_leading_decimal_point=config.allow_leading_decimal_point,
            issue_label=issue_label,
        )

    raise ValueError(f"Unsupported column config type: {type(config).__name__}")
