"""Post-transform quality metrics."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import quote_identifier
from shared.models.normalization import QualityOutput

from conversion.constants import PARSE_ERROR_COUNT_COLUMN

_HUNDRED = Decimal("100")


def _compute_quality_score(
    parse_success_ratio: float,
    completeness_ratio: float,
) -> Decimal:
    """
    Compute weighted quality score using deterministic Decimal arithmetic.

    Score formula (post-transform factors only):
      0.50 * parse_success_ratio
      0.50 * completeness_ratio

    Returns a value in [0, 100].
    """
    parse_success = _ratio_decimal(parse_success_ratio)
    completeness = _ratio_decimal(completeness_ratio)
    return (Decimal("0.50") * parse_success + Decimal("0.50") * completeness) * _HUNDRED


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

    # Single-pass: row count + per-column null counts
    null_exprs = [
        f"COUNT(*) FILTER (WHERE {quote_identifier(col)} IS NULL)"
        for col in columns
    ]
    aggregate_exprs = [
        "COUNT(*)",
        f"COALESCE(SUM({PARSE_ERROR_COUNT_COLUMN}), 0)",
        *null_exprs,
    ]
    null_query = f"SELECT {', '.join(aggregate_exprs)} FROM {RAW_INPUT_TABLE_NAME}"
    row = fetch_aggregate_int_row(conn, null_query)
    row_count, total_parse_error_cells, *column_null_values = row
    column_null_counts = dict(zip(columns, column_null_values, strict=True))
    total_nullish_cells = sum(column_null_counts.values())
    total_cells = row_count * len(columns)

    total_non_null_cells = total_cells - total_nullish_cells
    completeness_ratio = safe_ratio(total_non_null_cells, total_cells)
    parse_success_ratio = 1.0 - safe_ratio(
        total_parse_error_cells,
        total_non_null_cells,
        default=0.0,
    )
    quality_score = _compute_quality_score(parse_success_ratio, completeness_ratio)

    return QualityOutput(
        row_count=row_count,
        total_cells=total_cells,
        total_nullish_cells=total_nullish_cells,
        total_parse_error_cells=total_parse_error_cells,
        parse_success_ratio=parse_success_ratio,
        completeness_ratio=completeness_ratio,
        quality_score=str(quality_score),
        column_null_counts=column_null_counts,
    )
