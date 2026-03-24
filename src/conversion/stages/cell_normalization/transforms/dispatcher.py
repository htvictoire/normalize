"""Type dispatcher for cell normalization SQL expressions."""

from __future__ import annotations

from conversion.stages.cell_normalization.transforms.boolean import build_boolean_exprs
from conversion.stages.cell_normalization.transforms.date import build_date_exprs
from conversion.stages.cell_normalization.transforms.numeric import (
    build_decimal_exprs,
    build_integer_exprs,
)
from shared.column_parsing.normalizer import build_value_candidate_expr
from shared.models.column import (
    AccountingColumnConfig,
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
    StringColumnConfig,
)


def build_column_exprs(
    column_name: str,
    config: ColumnConfig,
    nullish_predicate: str,
    *,
    raw_value: str,
    normalized_raw_value: str,
) -> tuple[list[tuple[str, str]], str, str]:
    """Route to the appropriate type-specific expression builder.

    Returns (parse_cte_entries, normalized_expr, issue_expr).
    """
    if isinstance(config, StringColumnConfig):
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {raw_value} END"
        return ([], normalized, "NULL")

    if isinstance(config, BooleanColumnConfig):
        return build_boolean_exprs(
            nullish_predicate,
            normalized_raw_value,
            true_tokens=config.true_tokens,
            false_tokens=config.false_tokens,
        )

    if isinstance(config, DateColumnConfig):
        return build_date_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            date_format=config.date_format,
        )

    if isinstance(config, IntegerColumnConfig):
        return build_integer_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            thousand_separator=config.thousand_separator,
            grouping_style=config.grouping_style,
        )

    # Decimal-family: preprocess via the shared normalizer, then build decimal exprs.
    candidate = build_value_candidate_expr(raw_value, config)
    issue_label = f"INVALID_{config.type.upper()}"

    if isinstance(
        config,
        DecimalColumnConfig
        | CurrencyColumnConfig
        | PercentageColumnConfig
        | SignedColumnConfig
        | AccountingColumnConfig,
    ):
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

    raise ValueError(f"UNSUPPORTED_CONFIG_TYPE:{type(config).__name__}")
