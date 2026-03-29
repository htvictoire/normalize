"""Post-transform quality metrics."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, quote_identifier
from shared.models.normalization import QualityOutput

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
        f" AS {quote_identifier(col + '__nulls')}"
        for col in columns
    ]
    null_query = f"SELECT COUNT(*), {', '.join(null_exprs)} FROM {RAW_INPUT_TABLE_NAME}"
    row = conn.execute(null_query).fetchone()

    row_count = int(row[0])  # type: ignore[index]  # COUNT aggregate always returns 1 row; fetchone() is non-None
    column_null_counts = {col: int(row[i + 1]) for i, col in enumerate(columns)}  # type: ignore[index]  # same
    total_nullish_cells = sum(column_null_counts.values())
    total_cells = row_count * len(columns)

    total_parse_error_cells = execute_scalar(
        conn,
        f"SELECT COALESCE(SUM(_parse_error_count), 0) FROM {RAW_INPUT_TABLE_NAME}",
    )

    total_non_null_cells = total_cells - total_nullish_cells
    completeness_ratio = 1.0 if total_cells <= 0 else (total_non_null_cells / total_cells)
    parse_success_ratio = (
        1.0
        if total_non_null_cells <= 0
        else 1.0 - (total_parse_error_cells / total_non_null_cells)
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
