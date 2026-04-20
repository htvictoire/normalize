"""Cell normalization planning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from shared.db.sql import quote_identifier
from shared.models.column import ColumnConfig

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
    full_raw_row: bool = False,
    emit_raw_row: bool = True,
    emit_parse_issues: bool = True,
) -> CellPlan:
    """
    Derives per-column SQL expressions from the confirmed column configs and
    assembles them into a CellPlan for the transform.
    """
    data_columns = list(columns)

    parse_cte_entries: list[tuple[str, str]] = []
    base_exprs: list[str] = []
    raw_source_pairs: list[str] = []
    issue_pairs: list[str] = []

    for column_name in data_columns:
        spec = column_config[column_name]
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
            column_name, spec, nullish_alias,
            raw_value=raw_alias,
            normalized_raw_value=lower_alias,
        )
        parse_cte_entries.extend(col_exprs.parse_cte_entries)

        issue_col = issue_alias(column_name)
        base_exprs.append(f"{col_exprs.normalized_expr} AS {quote_identifier(column_name)}")
        base_exprs.append(f"{col_exprs.issue_expr} AS {quote_identifier(issue_col)}")

        if emit_raw_row:
            raw_source_pairs.append(
                f"{quote_identifier(column_name)} := "
                f"CAST({raw_alias} AS VARCHAR)"
            )
        if emit_parse_issues:
            issue_pairs.append(f"{quote_identifier(column_name)} := {quote_identifier(issue_col)}")

    return CellPlan(
        data_columns=tuple(data_columns),
        parse_cte_exprs=tuple(parse_cte_entries),
        column_select_exprs=tuple(base_exprs),
        raw_source_pairs=tuple(raw_source_pairs),
        issue_pairs=tuple(issue_pairs),
        emit_raw_row=emit_raw_row,
        full_raw_row=full_raw_row,
        emit_parse_issues=emit_parse_issues,
    )
