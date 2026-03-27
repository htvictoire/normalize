"""Post-transform quality metrics stage."""

from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, quote_identifier
from shared.models.normalization import QualityOutput
from shared.stage import Stage

from conversion.core.quality import compute_quality_score


class QualityMetricsStage(Stage):
    """
    Compute post-transform quality metrics from the normalized DuckDB table.

    Reads parse error counts and null counts after cell normalization transforms
    have run. All metrics are post-transform only — pre-transform data fitness
    is the responsibility of the profiling phase.
    """

    def execute(
        self,
        conn: DuckDBPyConnection,
        data_columns: Sequence[str],
    ) -> QualityOutput:
        """Return quality metrics derived from post-transform table state."""
        start = perf_counter()

        columns = list(data_columns)

        if not columns:
            self.metrics = {"duration_seconds": perf_counter() - start}
            return QualityOutput(
                row_count=0,
                total_cells=0,
                total_nullish_cells=0,
                total_parse_error_cells=0,
                parse_success_ratio=1.0,
                completeness_ratio=1.0,
                quality_score=str(compute_quality_score(1.0, 1.0)),
                column_null_counts={},
            )

        # Single-pass: row count + per-column null counts
        null_exprs = [
            f"COUNT(*) FILTER (WHERE {quote_identifier(col)} IS NULL)"
            f" AS {quote_identifier(col + '__nulls')}"
            for col in columns
        ]
        null_query = f"SELECT COUNT(*), {', '.join(null_exprs)} FROM {RAW_INPUT_TABLE_NAME}"
        row = conn.execute(null_query).fetchone()

        row_count = int(row[0])  # type: ignore[index]
        column_null_counts = {col: int(row[i + 1]) for i, col in enumerate(columns)}  # type: ignore[index]
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
        quality_score = compute_quality_score(parse_success_ratio, completeness_ratio)

        self.metrics = {
            "duration_seconds": perf_counter() - start,
            "row_count": row_count,
            "column_count": len(columns),
            "total_parse_error_cells": total_parse_error_cells,
            "total_nullish_cells": total_nullish_cells,
        }

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
