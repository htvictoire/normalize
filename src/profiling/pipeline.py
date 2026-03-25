"""Profiling pipeline — measures the full dataset against the confirmed config.

Phase 1  Resolve the ingestion source (local path or S3 URL, temp-file download
         for S3 Excel) and ingest into a DuckDB in-memory table.

Phase 2  Canonicalize headers and compute row/null counts for the live table.

Phase 3  Compute per-column profiles and data-quality issues from the live table.

Phase 4  Assemble and return the ProfilingOutput.
"""

from __future__ import annotations

from conversion.stages.header_canonicalization import HeaderCanonicalizationStage
from profiling.counts import compute_profiling_stats
from profiling.profiles import compute_profile_results
from shared.db.duckdb import DuckDBManager, configure_duckdb_s3
from shared.db.sql import read_columns
from shared.ingestion import (
    IngestionRequest,
    cleanup_ingestion_setup,
    resolve_ingestion_setup,
    run_ingestion,
)
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, SourceFormat
from shared.models.profiling import ProfilingOutput
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
            profiling_stats = compute_profiling_stats(
                conn,
                table_name="raw_input",
                position_to_name=position_to_name,
                null_tokens=operation_config.null_tokens,
            )
            profile_results = compute_profile_results(
                conn,
                position_to_name=position_to_name,
                column_config=column_config,
                null_tokens=operation_config.null_tokens,
                counts_by_position=profiling_stats.column_counts,
                row_count=profiling_stats.row_count,
            )
    finally:
        cleanup_ingestion_setup(setup)

    return ProfilingOutput(
        source_checksum=source_checksum,
        row_count=profiling_stats.row_count,
        empty_row_count=profiling_stats.empty_row_count,
        column_count=len(canonical_columns),
        pattern_consistency_ratio=profile_results.pattern_consistency_ratio,
        completeness_ratio=profile_results.completeness_ratio,
        column_stats=profile_results.column_stats,
        issues=profile_results.issues,
    )
