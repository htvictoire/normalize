"""Quality metrics stage."""

from __future__ import annotations

from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.token_policy import TokenPolicy
from normalize.stages.base import Stage
from normalize.stages.quality_metrics.queries import (
    read_detailed_column_stats,
    read_parse_error_stats,
    read_precomputed_column_null_stats,
    read_precomputed_row_count,
    read_precomputed_total_nullish_cells,
    read_total_parse_error_cells,
    read_unique_stats,
)
from normalize.stages.quality_metrics.sql_helpers import (
    read_data_columns,
    table_exists,
    validate_identifier,
)
from normalize.stages.shared_profiling import (
    DEFAULT_PROFILE_TABLE_NAME,
    ensure_column_profiles,
)


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
        table_name: str = "raw_input",
        profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
        null_tokens: list[str] | None,
        boolean_true_tokens: list[str] | None,
        boolean_false_tokens: list[str] | None,
        decimal_separator: str = ".",
        thousand_separator: str = "",
        allow_leading_decimal_point: bool = False,
        include_unique_ratio: bool = False,
        include_per_column_parse_error_counts: bool = False,
        approximate_unique: bool = False,
    ) -> dict[str, object]:
        start_time = perf_counter()
        validate_identifier(table_name)
        validate_identifier(profile_table_name)
        token_policy = TokenPolicy.from_user_inputs(
            null_tokens=null_tokens,
            boolean_true_tokens=boolean_true_tokens,
            boolean_false_tokens=boolean_false_tokens,
        )

        columns = read_data_columns(conn, table_name)
        use_precomputed_quality = table_exists(conn, "_quality_profile_raw_input")
        profiles = None
        precomputed_null_stats: dict[str, dict[str, int]] | None = None
        if use_precomputed_quality:
            precomputed_null_stats = read_precomputed_column_null_stats(conn)
        else:
            profiles = ensure_column_profiles(
                conn,
                table_name=table_name,
                profile_table_name=profile_table_name,
                token_policy=token_policy,
                decimal_separator=decimal_separator,
                thousand_separator=thousand_separator,
                allow_leading_decimal_point=allow_leading_decimal_point,
            )
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

        if use_precomputed_quality:
            row_count = read_precomputed_row_count(conn)
            total_nullish_cells = read_precomputed_total_nullish_cells(conn)
        else:
            if profiles is None:
                raise RuntimeError("profiles are required when precomputed quality table is absent")
            row_count = next(iter(profiles.values())).row_count if profiles else 0
            total_nullish_cells = sum(profile.nullish_count for profile in profiles.values())
        total_cells = row_count * len(columns)
        total_parse_error_cells = read_total_parse_error_cells(
            conn,
            table_name=table_name,
            columns=columns,
        )
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
            if use_precomputed_quality:
                if precomputed_null_stats is None:
                    raise RuntimeError("missing precomputed column null stats")
                stats = precomputed_null_stats.get(column_name)
                if stats is None:
                    raise RuntimeError(f"missing precomputed stats for column: {column_name}")
                null_ratio = 0.0 if row_count <= 0 else (stats["nullish_count"] / row_count)
            else:
                if profiles is None:
                    raise RuntimeError(
                        "profiles are required when precomputed quality table is absent"
                    )
                profile = profiles[column_name]
                null_ratio = profile.null_ratio
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
            "use_precomputed_quality": use_precomputed_quality,
        }
        return result
