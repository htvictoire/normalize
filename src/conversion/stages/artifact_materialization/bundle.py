"""Local artifact staging helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from duckdb import DuckDBPyConnection

from conversion.stages.artifact_materialization.constants import AUDIT_OUTPUT_COLUMNS
from conversion.stages.artifact_materialization.export import (
    build_export_columns,
    write_normalized_parquet,
)
from conversion.stages.artifact_materialization.manifest import (
    build_manifest_payload,
    write_manifest,
)
from conversion.stages.artifact_materialization.trace import write_trace_parquet
from conversion.utils.checksums import sha256_file
from shared.db.sql import read_columns
from shared.models.issues import NormalizationIssue
from shared.models.normalization import QualityOutput, SourceChecksums


@dataclass(frozen=True)
class StagedArtifacts:
    """Artifact files staged on a local filesystem root."""

    normalized_path: Path
    manifest_path: Path
    trace_path: Path
    data_column_count: int


def stage_artifacts(
    conn: DuckDBPyConnection,
    *,
    output_root: Path,
    fingerprint: str,
    quality_output: QualityOutput,
    source_checksums: SourceChecksums,
    issues: Sequence[NormalizationIssue],
    effective_config: Mapping[str, Any],
    trace_mode: str,
    table_name: str,
    stage_metrics: Mapping[str, Mapping[str, Any]] | None,
    rules_version: str,
    timing: dict[str, float],
) -> StagedArtifacts:
    """Write staged artifact files to one local directory."""
    output_root.mkdir(parents=True, exist_ok=True)

    normalized_path = output_root / f"{fingerprint}.parquet"
    manifest_path = output_root / f"{fingerprint}.manifest.json"
    trace_path = output_root / f"{fingerprint}.trace.parquet"

    section_start = perf_counter()
    table_columns = read_columns(conn, table_name)
    export_columns = build_export_columns(table_columns)
    data_columns = [col for col in export_columns if col not in AUDIT_OUTPUT_COLUMNS]
    timing["prepare_columns_seconds"] = perf_counter() - section_start

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

    section_start = perf_counter()
    normalized_checksum = sha256_file(normalized_path)
    trace_checksum = sha256_file(trace_path)
    timing["checksum_seconds"] = perf_counter() - section_start

    section_start = perf_counter()
    duckdb_version_row = conn.execute("SELECT version()").fetchone()
    if duckdb_version_row is None:
        raise RuntimeError("duckdb version query returned no rows")
    duckdb_version = str(duckdb_version_row[0])
    timing["duckdb_version_read_seconds"] = perf_counter() - section_start

    section_start = perf_counter()
    manifest = build_manifest_payload(
        fingerprint=fingerprint,
        source_checksums=source_checksums,
        stage_metrics=stage_metrics or {},
        quality_output=quality_output,
        issues=list(issues),
        normalized_checksum=normalized_checksum,
        trace_checksum=trace_checksum,
        effective_config=effective_config,
        rules_version=rules_version,
        duckdb_version=duckdb_version,
        normalized_path=normalized_path,
        trace_path=trace_path,
        manifest_path=manifest_path,
    )
    write_manifest(manifest_path, manifest)
    timing["manifest_write_seconds"] = perf_counter() - section_start

    return StagedArtifacts(
        normalized_path=normalized_path,
        manifest_path=manifest_path,
        trace_path=trace_path,
        data_column_count=len(data_columns),
    )
