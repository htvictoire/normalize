"""Post-transform quality metrics."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import quote_identifier, quote_string
from shared.models.normalization import QualityOutput

from conversion.constants import PARSE_ERROR_COUNT_COLUMN, PARSE_ISSUES_COLUMN

_HUNDRED = Decimal("100")


def _compute_quality_score(parse_success_ratio: float) -> Decimal:
    """Fidelity as a 0-100 Decimal: of the cells that carried a value, what survived.

    Completeness is not a factor. It measures how full the source was, which this
    pipeline does not control, and the score gates readiness — scoring density
    would block correct output for a sparse source.
    """
    return _ratio_decimal(parse_success_ratio) * _HUNDRED


def _ratio_decimal(value: float) -> Decimal:
    ratio = Decimal(str(value))
    if ratio < Decimal("0") or ratio > Decimal("1"):
        raise ValueError(f"ratio must be between 0 and 1, got {value}")
    return ratio


def compute_quality(
    conn: DuckDBPyConnection,
    data_columns: Sequence[str],
) -> QualityOutput:
    """
    Parse success and null completeness metrics over the normalized table.

    Operates on post-transform data only — pre-transform fitness is the
    profiling phase's concern.
    """
    columns = list(data_columns)

    # Single pass: row count, per-column nulls, per-column failures. Failures come
    # from _parse_issues, which holds an entry for every cell that had a value and
    # lost it -- so nulls minus failures is exactly the cells the source left empty.
    null_exprs = [
        f"COUNT(*) FILTER (WHERE {quote_identifier(col)} IS NULL)"
        for col in columns
    ]
    error_exprs = [
        f"COUNT(*) FILTER (WHERE JSON_EXTRACT_STRING({PARSE_ISSUES_COLUMN}, "
        f"{quote_string(f'$.{col}.code')}) IS NOT NULL)"
        for col in columns
    ]
    aggregate_exprs = [
        "COUNT(*)",
        f"COALESCE(SUM({PARSE_ERROR_COUNT_COLUMN}), 0)",
        *null_exprs,
        *error_exprs,
    ]
    null_query = f"SELECT {', '.join(aggregate_exprs)} FROM {RAW_INPUT_TABLE_NAME}"
    row = fetch_aggregate_int_row(conn, null_query)
    row_count, total_parse_error_cells, *rest = row
    column_null_values = rest[: len(columns)]
    column_error_values = rest[len(columns) :]
    column_null_counts = dict(zip(columns, column_null_values, strict=True))
    column_parse_error_counts = dict(zip(columns, column_error_values, strict=True))
    total_nullish_cells = sum(column_null_counts.values())
    total_cells = row_count * len(columns)
    total_non_null_cells = total_cells - total_nullish_cells

    total_original_null_cells = total_nullish_cells - total_parse_error_cells
    total_attempted_cells = total_cells - total_original_null_cells

    completeness_ratio = safe_ratio(total_non_null_cells, total_cells)
    # Denominator is what was attempted, never what survived: dividing by survivors
    # yields an odds ratio, which passes 1.0 once failures outnumber successes.
    parse_success_ratio = 1.0 - safe_ratio(
        total_parse_error_cells,
        total_attempted_cells,
        default=0.0,  # nothing to parse means nothing was lost
    )
    quality_score = _compute_quality_score(parse_success_ratio)

    # A mean hides an annihilated column -- one dead column in twenty still scores 95 --
    # so the worst column is reported separately and gated on in evaluate_decision.
    column_parse_success_ratios = {
        col: _column_parse_success_ratio(
            row_count=row_count,
            null_count=column_null_counts[col],
            error_count=column_parse_error_counts[col],
        )
        for col in columns
    }
    worst = min(column_parse_success_ratios.values(), default=1.0)

    return QualityOutput(
        row_count=row_count,
        total_cells=total_cells,
        total_nullish_cells=total_nullish_cells,
        total_original_null_cells=total_original_null_cells,
        total_parse_error_cells=total_parse_error_cells,
        total_attempted_cells=total_attempted_cells,
        parse_success_ratio=parse_success_ratio,
        completeness_ratio=completeness_ratio,
        quality_score=str(quality_score),
        worst_column_score=str(_compute_quality_score(worst)),
        column_null_counts=column_null_counts,
        column_parse_error_counts=column_parse_error_counts,
        column_parse_success_ratios=column_parse_success_ratios,
    )


def _column_parse_success_ratio(row_count: int, null_count: int, error_count: int) -> float:
    """Fidelity for one column: of the cells that carried a value, what survived."""
    original_nulls = null_count - error_count
    attempted = row_count - original_nulls
    return 1.0 - safe_ratio(error_count, attempted, default=0.0)
