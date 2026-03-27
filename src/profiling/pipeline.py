"""Profiling pipeline — measures the full dataset against the confirmed config.

Phase 1  Resolve the ingestion source (local path or S3 URL, temp-file download
         for S3 Excel) and ingest into a file-backed DuckDB table so the
         conversion phase can reuse it without re-ingesting.

Phase 2  Canonicalize headers and compute row/null counts for the live table.

Phase 3  Compute per-column profiles and data-quality issues from the live table.

Phase 4  Assemble and return the ProfilingOutput.
"""

from __future__ import annotations

from pathlib import Path

from shared.db.column_index import build_position_to_name
from shared.db.duckdb import DuckDBManager, configure_duckdb_s3, resolve_db_path
from shared.db.sql import read_columns
from shared.ingestion import (
    IngestionRequest,
    cleanup_ingestion_setup,
    resolve_ingestion_setup,
    run_ingestion,
)
from shared.ingestion.canonicalization import HeaderCanonicalizationStage
from shared.models.instance_config import InstanceConfig
from shared.models.profiling import ProfilingOutput
from shared.models.source import SourceRef

from profiling.counts import compute_profiling_stats
from profiling.profiles import compute_profile_results


def run_profiling(
    source: SourceRef,
    *,
    source_checksum: str,
    confirmed_config: InstanceConfig,
    persisted_db_path: Path,
) -> ProfilingOutput:
    """Run the full-dataset profiling phase using confirmed config.

    The DuckDB table is written to persisted_db_path so the conversion phase
    can open it directly without re-ingesting the source file.
    """
    db_arg = resolve_db_path(str(persisted_db_path))
    setup = resolve_ingestion_setup(source, confirmed_config.source_format)
    try:
        with DuckDBManager(database=db_arg) as conn:
            if setup.source_type == "s3":
                configure_duckdb_s3(conn)
            run_ingestion(
                IngestionRequest(
                    conn=conn,
                    source_url=setup.url,
                    source_type=setup.source_type,
                    source_format=confirmed_config.source_format,
                )
            )

            HeaderCanonicalizationStage().execute(conn)
            canonical_columns = read_columns(conn)
            position_to_name = build_position_to_name(canonical_columns)
            profiling_stats = compute_profiling_stats(
                conn,
                position_to_name=position_to_name,
                null_tokens=confirmed_config.operation_config.null_tokens,
            )
            profile_results = compute_profile_results(
                conn,
                position_to_name=position_to_name,
                column_config=confirmed_config.column_config,
                null_tokens=confirmed_config.operation_config.null_tokens,
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
