"""Plan data contracts for the combined row+cell transform."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.normalization import QualityOutput


@dataclass(frozen=True)
class RowPlan:
    """SQL fragments produced by row normalization planning."""

    filter_predicate: str | None  # None = no filtering
    assign_indices: bool
    rows_dropped: int  # known from a cheap pre-check


@dataclass(frozen=True)
class CellPlan:
    """SQL fragments produced by cell normalization planning."""

    data_columns: tuple[str, ...]
    # (alias, expr) pairs for the pre-parse CTE — materialised once per row
    # so expensive sub-expressions (REGEXP_FULL_MATCH, TRY_CAST, TRY_STRPTIME)
    # are not re-evaluated for both the normalized value and the issue code.
    parse_cte_exprs: tuple[tuple[str, str], ...]
    # SELECT expressions for the base CTE:
    #   normalized column AS col, issue expr AS __issue__col
    column_select_exprs: tuple[str, ...]
    # Pairs for TO_JSON(STRUCT_PACK(...)) capturing pre-cast values
    raw_source_pairs: tuple[str, ...]
    # Pairs for TO_JSON(STRUCT_PACK(...)) capturing issue codes
    issue_pairs: tuple[str, ...]
    # Expression summing per-column error indicators
    row_error_expr: str
    # Final _raw_row expression (may be conditional on _parse_error_count)
    raw_row_expr: str
    # Final _parse_issues expression (may be conditional on _parse_error_count)
    parse_issues_expr: str
    emit_raw_row: bool
    full_raw_row: bool
    emit_parse_issues: bool


@dataclass(frozen=True)
class TransformResult:
    """Output of the conversion computation — quality metrics and the plans that shaped the transform."""

    quality_output: QualityOutput
    cell_plan: CellPlan
    row_plan: RowPlan
