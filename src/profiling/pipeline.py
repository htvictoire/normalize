"""Profiling pipeline — measures the full dataset against the confirmed config.

Phase 1  Ingest source data into the file-backed DuckDB table.
Phase 2  Canonicalize headers and compute row/null counts for the live table.
Phase 3  Compute per-column profiles and data-quality issues from the live table.
Phase 4  Assemble and return the ProfilingOutput.
"""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.column_index import build_position_to_name
from shared.db.sql import read_columns
from shared.ingestion import IngestionRequest, IngestionSetup, run_ingestion
from shared.ingestion.canonicalization import canonicalize_table_headers
from shared.models.instance_config import InstanceConfig
from shared.models.profiling import ProfilingOutput

from profiling.counts import compute_profiling_stats
from profiling.profiles import compute_profile_results


def run_profiling(
    conn: DuckDBPyConnection,
    setup: IngestionSetup,
    source_checksum: str,
    confirmed_config: InstanceConfig,
) -> ProfilingOutput:
    """Run the full-dataset profiling phase using confirmed config."""
    run_ingestion(
        IngestionRequest(
            conn=conn,
            source_url=setup.url,
            source_type=setup.source_type,
            source_format=confirmed_config.source_format,
        )
    )

    canonicalize_table_headers(conn)
    canonical_columns = read_columns(conn)
    position_to_name = build_position_to_name(canonical_columns)
    profiling_stats = compute_profiling_stats(
        conn=conn,
        position_to_name=position_to_name,
        null_tokens=confirmed_config.operation_config.null_tokens,
    )
    profile_results = compute_profile_results(
        conn=conn,
        position_to_name=position_to_name,
        column_config=confirmed_config.column_config,
        null_tokens=confirmed_config.operation_config.null_tokens,
        counts_by_position=profiling_stats.column_counts,
        row_count=profiling_stats.row_count,
    )
    return ProfilingOutput(
        source_checksum=source_checksum,
        row_count=profiling_stats.row_count,
        empty_row_count=profiling_stats.empty_row_count,
        column_count=len(canonical_columns),
        pattern_consistency_ratio=profile_results.mean_dominant_symbol_ratio,
        completeness_ratio=profile_results.completeness_ratio,
        column_stats=profile_results.column_stats,
        issues=profile_results.issues,
    )
