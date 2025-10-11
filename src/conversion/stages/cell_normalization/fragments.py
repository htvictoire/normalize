"""Cell expression fragment builders shared by plan/execute paths."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from conversion.core.token_policy import TokenPolicy
from conversion.stages.cell_normalization.naming import (
    issue_alias,
    parse_lower_alias,
    parse_nullish_alias,
    parse_raw_alias,
)
from conversion.stages.cell_normalization.sql_helpers import quote_identifier
from conversion.stages.cell_normalization.transforms.dispatcher import build_column_exprs
from conversion.stages.cell_normalization.transforms.nullish import build_nullish_predicate
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
    column_config_type,
)


@dataclass(frozen=True)
class CellExpressionFragments:
    """SQL fragment groups derived from inferred types and token policy."""

    parse_cte_entries: tuple[tuple[str, str], ...]
    base_exprs: tuple[str, ...]
    raw_source_pairs: tuple[str, ...]
    issue_pairs: tuple[str, ...]
    row_error_terms: tuple[str, ...]


def build_cell_expression_fragments(
    *,
    data_columns: Sequence[str],
    column_config: Mapping[str, ColumnConfig],
    token_policy: TokenPolicy,
    emit_raw_row: bool,
    emit_parse_issues: bool,
) -> CellExpressionFragments:
    """Build reusable SQL fragments for both `plan()` and `execute()`."""
    parse_cte_entries: list[tuple[str, str]] = []
    base_exprs: list[str] = []
    raw_source_pairs: list[str] = []
    issue_pairs: list[str] = []
    row_error_terms: list[str] = []

    for column_name in data_columns:
        spec = column_config[column_name]
        inferred_type = column_config_type(spec)
        quoted_column = quote_identifier(column_name)
        raw_alias = quote_identifier(parse_raw_alias(column_name))
        lower_alias = quote_identifier(parse_lower_alias(column_name))
        nullish_alias = quote_identifier(parse_nullish_alias(column_name))
        parse_cte_entries.append((raw_alias, f"CAST({quoted_column} AS VARCHAR)"))
        parse_cte_entries.append((lower_alias, f"LOWER(TRIM({raw_alias}))"))
        parse_cte_entries.append(
            (
                nullish_alias,
                build_nullish_predicate(raw_alias, lower_alias, token_policy.null_tokens),
            )
        )
        column_decimal_separator: str
        column_thousand_separator: str
        column_grouping_style: str
        if isinstance(spec, IntegerColumnConfig):
            column_decimal_separator = ""
            column_thousand_separator = spec.thousand_separator
            column_grouping_style = spec.grouping_style
            allow_leading_decimal_point = False
        elif isinstance(spec, DecimalColumnConfig | CurrencyColumnConfig | PercentageColumnConfig | SignedColumnConfig | AccountingColumnConfig):  # noqa: E501
            column_decimal_separator = spec.decimal_separator
            column_thousand_separator = spec.thousand_separator
            column_grouping_style = spec.grouping_style
            allow_leading_decimal_point = spec.allow_leading_decimal_point
        else:
            column_decimal_separator = ""
            column_thousand_separator = ""
            column_grouping_style = ""
            allow_leading_decimal_point = False
        date_format = spec.date_format if isinstance(spec, DateColumnConfig) else None
        true_tokens: tuple[str, ...] = (
            spec.true_tokens if isinstance(spec, BooleanColumnConfig) else ()
        )
        false_tokens: tuple[str, ...] = (
            spec.false_tokens if isinstance(spec, BooleanColumnConfig) else ()
        )
        signed_spec: SignedColumnConfig | AccountingColumnConfig | None = (
            spec if isinstance(spec, SignedColumnConfig | AccountingColumnConfig) else None
        )
        positive_markers: tuple[str, ...] = (
            signed_spec.positive_markers if signed_spec is not None else ()
        )
        negative_markers: tuple[str, ...] = (
            signed_spec.negative_markers if signed_spec is not None else ()
        )
        parentheses_as_negative = (
            signed_spec.parentheses_as_negative if signed_spec is not None else False
        )
        col_parse_entries, normalized_expr, issue_expr = build_column_exprs(
            column_name,
            inferred_type,
            nullish_alias,
            raw_value=raw_alias,
            normalized_raw_value=lower_alias,
            true_tokens=true_tokens,
            false_tokens=false_tokens,
            decimal_separator=column_decimal_separator,
            thousand_separator=column_thousand_separator,
            grouping_style=column_grouping_style,
            allow_leading_decimal_point=allow_leading_decimal_point,
            date_format=date_format,
            positive_markers=positive_markers,
            negative_markers=negative_markers,
            parentheses_as_negative=parentheses_as_negative,
        )
        parse_cte_entries.extend(col_parse_entries)
        issue_col = issue_alias(column_name)
        base_exprs.append(f"{normalized_expr} AS {quote_identifier(column_name)}")
        base_exprs.append(f"{issue_expr} AS {quote_identifier(issue_col)}")
        row_error_terms.append(f"CASE WHEN {quote_identifier(issue_col)} IS NULL THEN 0 ELSE 1 END")
        if emit_raw_row:
            raw_source_pairs.append(
                f"{quote_identifier(column_name)} := "
                f"CAST({quote_identifier(column_name)} AS VARCHAR)"
            )
        if emit_parse_issues:
            issue_pairs.append(f"{quote_identifier(column_name)} := {quote_identifier(issue_col)}")

    return CellExpressionFragments(
        parse_cte_entries=tuple(parse_cte_entries),
        base_exprs=tuple(base_exprs),
        raw_source_pairs=tuple(raw_source_pairs),
        issue_pairs=tuple(issue_pairs),
        row_error_terms=tuple(row_error_terms),
    )
