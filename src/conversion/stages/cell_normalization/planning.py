"""Plan assembly helpers for cell normalization."""

from __future__ import annotations

from conversion.core.transform.models import CellPlan
from conversion.stages.cell_normalization.fragments import CellExpressionFragments


def build_cell_plan(
    data_columns: tuple[str, ...],
    fragments: CellExpressionFragments,
    full_raw_row: bool,
    emit_raw_row: bool,
    emit_parse_issues: bool,
) -> CellPlan:
    """Build a `CellPlan` from prepared SQL fragments."""
    row_error_expr = "0" if not fragments.row_error_terms else " + ".join(fragments.row_error_terms)

    if emit_raw_row:
        full_raw_row_expr = "__raw_json"
        if full_raw_row:
            raw_row_expr = full_raw_row_expr
        else:
            raw_row_expr = (
                f"CASE WHEN _parse_error_count = 0 THEN NULL ELSE {full_raw_row_expr} END"
            )
    else:
        raw_row_expr = "NULL::VARCHAR"

    if emit_parse_issues:
        parse_issues_expr = (
            "CASE WHEN _parse_error_count = 0 THEN NULL "
            f"ELSE TO_JSON(STRUCT_PACK({', '.join(fragments.issue_pairs)})) END"
        )
    else:
        parse_issues_expr = "NULL::VARCHAR"

    return CellPlan(
        data_columns=data_columns,
        parse_cte_exprs=fragments.parse_cte_entries,
        column_select_exprs=fragments.base_exprs,
        raw_source_pairs=fragments.raw_source_pairs,
        issue_pairs=fragments.issue_pairs,
        row_error_expr=row_error_expr,
        raw_row_expr=raw_row_expr,
        parse_issues_expr=parse_issues_expr,
        emit_raw_row=emit_raw_row,
        full_raw_row=full_raw_row,
        emit_parse_issues=emit_parse_issues,
    )
