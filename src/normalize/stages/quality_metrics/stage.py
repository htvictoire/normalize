"""Quality metrics stage."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.stages.quality_metrics.queries.detailed import read_detailed_column_stats
from normalize.stages.quality_metrics.queries.parse_errors import read_parse_error_stats
from normalize.stages.quality_metrics.queries.unique import read_unique_stats
from normalize.stages.quality_metrics.sql_helpers import (
    read_data_columns,
    validate_identifier,
)
from shared.stages.base import Stage


class QualityMetricsStage(Stage):
    """
    Compute per-column quality metrics and aggregate quality components.

    Returned structure:
    - row_count
    - total_cells
    - total_nullish_cells
    - total_parse_error_cells
    - parse_success_ratio
    - completeness_ratio
    - column_metrics map with null_ratio/unique_ratio/parse_error_count

    Uses the same explicit token policy as type inference and cell
    normalization so completeness and parse-success metrics are computed with
    identical null/boolean semantics.

    Performance modes:
    - default (`include_unique_ratio=False`, `include_per_column_parse_error_counts=False`)
      skips expensive per-column scans.
    - detailed mode enables exact unique ratios and/or per-column parse counts.
    """

    def execute(
        self,
        conn: DuckDBPyConnection,
        *,
        row_count: int,
        per_column_stats: Mapping[str, Mapping[str, int]],
        total_parse_error_cells: int,
        table_name: str = "raw_input",
        include_unique_ratio: bool = False,
        include_per_column_parse_error_counts: bool = False,
        approximate_unique: bool = False,
    ) -> dict[str, object]:
        start_time = perf_counter()
        validate_identifier(table_name)

        columns = read_data_columns(conn, table_name)
        if not columns:
            result: dict[str, object] = {
                "row_count": 0,
                "total_cells": 0,
                "total_nullish_cells": 0,
                "total_parse_error_cells": 0,
                "parse_success_ratio": 1.0,
                "completeness_ratio": 1.0,
                "column_metrics": {},
            }
            self.metrics = {
                "duration_seconds": perf_counter() - start_time,
                "row_count": 0,
                "column_count": 0,
            }
            return result

        total_nullish_cells = 0
        for column_name in columns:
            column_stats = per_column_stats.get(column_name)
            if column_stats is None:
                raise ValueError(f"per_column_stats missing column: {column_name}")
            total_nullish_cells += int(column_stats.get("nullish_count", 0))
        total_cells = row_count * len(columns)
        unique_stats: dict[str, dict[str, int]] | None = None
        detailed_stats: dict[str, dict[str, int]] | None = None
        if include_unique_ratio:
            if include_per_column_parse_error_counts:
                detailed_stats = read_detailed_column_stats(
                    conn,
                    table_name=table_name,
                    columns=columns,
                    approximate=approximate_unique,
                )
            else:
                unique_stats = read_unique_stats(
                    conn, table_name=table_name, columns=columns, approximate=approximate_unique
                )
        parse_error_stats: dict[str, int] | None = None
        if include_per_column_parse_error_counts and detailed_stats is None:
            parse_error_stats = read_parse_error_stats(conn, table_name=table_name, columns=columns)
        non_null_cells = max(total_cells - total_nullish_cells, 0)
        parse_success_ratio = 1.0
        if non_null_cells > 0:
            parse_success_ratio = max(0.0, 1.0 - (total_parse_error_cells / non_null_cells))
        completeness_ratio = 1.0
        if total_cells > 0:
            completeness_ratio = max(0.0, 1.0 - (total_nullish_cells / total_cells))

        column_metrics: dict[str, dict[str, float | int | None]] = {}
        for column_name in columns:
            stats = per_column_stats.get(column_name)
            if stats is None:
                raise ValueError(f"per_column_stats missing column: {column_name}")
            null_ratio = 0.0 if row_count <= 0 else (int(stats["nullish_count"]) / row_count)
            unique_ratio: float | None = None
            if detailed_stats is not None:
                stats = detailed_stats[column_name]
                if stats["non_null_count"] <= 0:
                    unique_ratio = 0.0
                else:
                    unique_ratio = stats["unique_non_null_count"] / stats["non_null_count"]
            elif unique_stats is not None:
                stats = unique_stats[column_name]
                if stats["non_null_count"] <= 0:
                    unique_ratio = 0.0
                else:
                    unique_ratio = stats["unique_non_null_count"] / stats["non_null_count"]
            parse_error_count: int | None = None
            if detailed_stats is not None:
                parse_error_count = detailed_stats[column_name]["parse_error_count"]
            elif parse_error_stats is not None:
                parse_error_count = parse_error_stats[column_name]
            column_metrics[column_name] = {
                "null_ratio": null_ratio,
                "unique_ratio": unique_ratio,
                "parse_error_count": parse_error_count,
            }

        result = {
            "row_count": row_count,
            "total_cells": total_cells,
            "total_nullish_cells": total_nullish_cells,
            "total_parse_error_cells": total_parse_error_cells,
            "parse_success_ratio": parse_success_ratio,
            "completeness_ratio": completeness_ratio,
            "column_metrics": column_metrics,
        }
        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "row_count": row_count,
            "column_count": len(columns),
            "total_parse_error_cells": total_parse_error_cells,
            "total_nullish_cells": total_nullish_cells,
            "include_unique_ratio": include_unique_ratio,
            "include_per_column_parse_error_counts": include_per_column_parse_error_counts,
        }
        return result
