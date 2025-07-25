"""Background ThreadPoolExecutor target functions for pipeline optimizations."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

import duckdb as _duckdb

from normalize.stages.artifact_materialization.export import (
    write_normalized_parquet,
)
from normalize.stages.artifact_materialization.trace import write_trace_parquet


def write_parquets_background(
    db_path: str,
    output_root: Path,
    fingerprint: str,
    trace_mode: str,
    table_name: str,
    export_columns: list[str],
    data_columns: list[str],
    table_columns: list[str],
) -> dict[str, float]:
    """Write parquet files on a second connection to the file-backed DB.

    Opens a separate connection (same config as the main writer) so COPY-TO
    can run concurrently with read-only quality-metrics work on the main
    connection.  Returns a timing dict with section durations.
    """
    timing: dict[str, float] = {}
    conn = _duckdb.connect(db_path)
    try:
        normalized_path = output_root / f"{fingerprint}.parquet"
        trace_path = output_root / f"{fingerprint}.trace.parquet"

        section_start = perf_counter()
        write_normalized_parquet(
            conn,
            normalized_path=normalized_path,
            table_name=table_name,
            export_columns=export_columns,
        )
        timing["write_normalized_parquet_seconds"] = perf_counter() - section_start

        section_start = perf_counter()
        sparse = trace_mode == "sparse"
        trace_pre_filter: str | None = None
        if sparse and "_parse_error_count" in table_columns:
            trace_pre_filter = "_parse_error_count > 0"
        write_trace_parquet(
            conn,
            trace_path=trace_path,
            table_name=table_name,
            data_columns=data_columns,
            table_columns=table_columns,
            sparse=sparse,
            row_pre_filter=trace_pre_filter,
        )
        timing["write_trace_parquet_seconds"] = perf_counter() - section_start

        return timing
    finally:
        conn.close()
