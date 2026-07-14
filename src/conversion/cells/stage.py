"""Cell normalization planning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from shared.db.sql import quote_identifier
from shared.models.column import ColumnConfig
from shared.models.profiling import ColumnProfileStats

from conversion.cells.exprs.dispatch import build_column_exprs
from conversion.cells.exprs.nullish import build_nullish_predicate
from conversion.cells.naming import (
    issue_alias,
    parse_lower_alias,
    parse_nullish_alias,
    parse_raw_alias,
)
from conversion.models import CellPlan


def plan_cells(
    column_config: Mapping[str, ColumnConfig],
    null_tokens: Sequence[str],
    columns: list[str],
    column_stats: Mapping[str, ColumnProfileStats],
    emit_raw_row: bool = False,
) -> CellPlan:
    """
    Derives per-column SQL expressions from the confirmed column configs and
    assembles them into a CellPlan for the transform.

    Every failing cell contributes its issue code *and* its original text; a
    normalized NULL is always attributable to either an empty source cell or a
    recorded parse failure.
    """
    data_columns = list(columns)

    parse_cte_entries: list[tuple[str, str]] = []
    base_exprs: list[str] = []
    raw_source_pairs: list[str] = []
    issue_pairs: list[str] = []

    for column_name in data_columns:
        spec = column_config[column_name]
        profile = column_stats[column_name].type_profile
        quoted_column = quote_identifier(column_name)
        raw_alias = quote_identifier(parse_raw_alias(column_name))
        lower_alias = quote_identifier(parse_lower_alias(column_name))
        nullish_alias = quote_identifier(parse_nullish_alias(column_name))

        parse_cte_entries.append((raw_alias, f"CAST({quoted_column} AS VARCHAR)"))
        parse_cte_entries.append((lower_alias, f"LOWER(TRIM({raw_alias}))"))
        parse_cte_entries.append(
            (nullish_alias, build_nullish_predicate(raw_alias, lower_alias, null_tokens))
        )

        col_exprs = build_column_exprs(
            column_name, spec, profile, nullish_alias,
            raw_value=raw_alias,
            normalized_raw_value=lower_alias,
        )
        parse_cte_entries.extend(col_exprs.parse_cte_entries)

        issue_col = quote_identifier(issue_alias(column_name))
        base_exprs.append(f"{col_exprs.normalized_expr} AS {quote_identifier(column_name)}")
        base_exprs.append(f"{col_exprs.issue_expr} AS {issue_col}")

        raw_source_pairs.append(
            f"{quote_identifier(column_name)} := CAST({raw_alias} AS VARCHAR)"
        )
        issue_pairs.append(
            f"{quote_identifier(column_name)} := "
            f"CASE WHEN {issue_col} IS NULL THEN NULL "
            f"ELSE json_object('raw', CAST({raw_alias} AS VARCHAR), 'code', {issue_col}) END"
        )

    return CellPlan(
        data_columns=tuple(data_columns),
        parse_cte_exprs=tuple(parse_cte_entries),
        column_select_exprs=tuple(base_exprs),
        raw_source_pairs=tuple(raw_source_pairs),
        issue_pairs=tuple(issue_pairs),
        emit_raw_row=emit_raw_row,
    )
