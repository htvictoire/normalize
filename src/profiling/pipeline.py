"""Profiling pipeline — measures the full dataset against the confirmed config.

Phase 1  Resolve the ingestion source (local path or S3 URL, temp-file download
         for S3 Excel) and ingest into a DuckDB in-memory table.

Phase 2  Compute row-level stats: total row count, empty row count, and per-column
         null/nullish counts using the confirmed null tokens.

Phase 3  For each configured column, compute the type-specific column profile and
         detect data-quality issues (mixed currency symbols, separator mismatch).

Phase 4  Assemble and return the ProfilingOutput.
"""

from __future__ import annotations

from conversion.stages.header_canonicalization import HeaderCanonicalizationStage
from profiling.column_stats import compute_column_profile, compute_global_stats
from profiling.constants import NUMERIC_MISMATCH_THRESHOLD
from profiling.issues import collect_column_issues
from shared.db.duckdb import DuckDBManager, configure_duckdb_s3
from shared.db.sql import compute_column_counts, read_columns
from shared.ingestion import (
    IngestionRequest,
    cleanup_ingestion_setup,
    resolve_ingestion_setup,
    run_ingestion,
)
from shared.models.column import ColumnConfig, column_config_type
from shared.models.operation import OperationConfig, SourceFormat
from shared.models.profiling import ColumnProfileStats, ProfilingOutput
from shared.models.source import SourceRef
from shared.utils.column import build_position_to_name


def run_profiling(
    source: SourceRef,
    *,
    source_checksum: str,
    source_format: SourceFormat,
    column_config: dict[str, ColumnConfig],
    operation_config: OperationConfig,
) -> ProfilingOutput:
    """Run the full-dataset profiling phase using confirmed config."""
    setup = resolve_ingestion_setup(source, source_format)
    try:
        with DuckDBManager() as conn:
            if setup.source_type == "s3":
                configure_duckdb_s3(conn)
            run_ingestion(
                IngestionRequest(
                    conn=conn,
                    source_url=setup.url,
                    source_type=setup.source_type,
                    source_format=source_format,
                    table_name="raw_input",
                )
            )

            HeaderCanonicalizationStage().execute(conn)
            canonical_columns = read_columns(conn, "raw_input")
            position_to_name = build_position_to_name(canonical_columns)

            row_count, empty_row_count = compute_global_stats(
                conn,
                table_name="raw_input",
                null_tokens=operation_config.null_tokens,
            )
            _, null_stats = compute_column_counts(
                conn,
                table_name="raw_input",
                position_to_name=position_to_name,
                null_tokens=operation_config.null_tokens,
            )

            issues = []
            column_stats: dict[str, ColumnProfileStats] = {}
            currency_ratios: list[float] = []
            total_non_nullish_cells = 0

            for pos, column_name in position_to_name.items():
                config = column_config.get(pos)
                if config is None:
                    continue

                counts = null_stats[pos]
                total_non_nullish_cells += counts.non_nullish_count
                null_ratio = 0.0 if row_count <= 0 else (counts.null_count / row_count)
                nullish_ratio = 0.0 if row_count <= 0 else (counts.nullish_count / row_count)

                type_profile = compute_column_profile(
                    conn,
                    column_name=column_name,
                    config=config,
                    null_tokens=operation_config.null_tokens,
                    counts=counts,
                )
                collect_column_issues(
                    column_name,
                    config,
                    type_profile,
                    issues,
                    currency_ratios,
                    numeric_threshold=NUMERIC_MISMATCH_THRESHOLD,
                )

                column_stats[pos] = ColumnProfileStats(
                    label=column_name,
                    column_type=column_config_type(config),
                    counts=counts,
                    null_ratio=null_ratio,
                    nullish_ratio=nullish_ratio,
                    type_profile=type_profile,
                )

            column_count = len(canonical_columns)
            total_cells = row_count * column_count
            completeness_ratio = (
                1.0 if total_cells <= 0 else (total_non_nullish_cells / total_cells)
            )
            pattern_consistency_ratio = (
                1.0 if not currency_ratios else (sum(currency_ratios) / len(currency_ratios))
            )
    finally:
        cleanup_ingestion_setup(setup)

    return ProfilingOutput(
        source_checksum=source_checksum,
        row_count=row_count,
        empty_row_count=empty_row_count,
        column_count=column_count,
        pattern_consistency_ratio=pattern_consistency_ratio,
        completeness_ratio=completeness_ratio,
        column_stats=column_stats,
        issues=issues,
    )
