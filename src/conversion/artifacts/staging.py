"""Local artifact file staging."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.db.duckdb import get_duckdb_version
from shared.models.issues import NormalizationIssue
from shared.models.operation import TraceMode

from conversion.artifacts.export import (
    build_export_columns,
    write_normalized_parquet,
)
from conversion.artifacts.manifest import (
    build_manifest_payload,
    write_manifest,
)
from conversion.artifacts.trace import write_trace_parquet
from conversion.constants import PARSE_ERROR_COUNT_COLUMN
from conversion.models import TransformResult


@dataclass(frozen=True)
class StagedArtifacts:
    """Artifact files staged on a local filesystem root."""

    normalized_path: Path
    manifest_path: Path
    trace_path: Path


def stage_artifacts(
    conn: DuckDBPyConnection,
    output_root: Path,
    result: TransformResult,
    source_checksum: str,
    issues: Sequence[NormalizationIssue],
    trace_mode: TraceMode,
    full_raw_row: bool,
) -> StagedArtifacts:
    """Write staged artifact files to one local directory."""
    output_root.mkdir(parents=True, exist_ok=True)

    normalized_path = output_root / "normalized.parquet"
    manifest_path = output_root / "manifest.json"
    trace_path = output_root / "trace.parquet"

    data_columns = list(result.cell_plan.data_columns)
    export_columns = build_export_columns(data_columns, full_raw_row=full_raw_row)

    write_normalized_parquet(
        conn,
        normalized_path=normalized_path,
        export_columns=export_columns,
    )

    # Skipping clean rows is only valid when the trace wants failures alone.
    trace_pre_filter: str | None = None
    if trace_mode == frozenset({"issues"}):
        trace_pre_filter = f"{PARSE_ERROR_COUNT_COLUMN} > 0"
    write_trace_parquet(
        conn,
        trace_path=trace_path,
        data_columns=data_columns,
        trace_mode=trace_mode,
        has_raw_row=result.cell_plan.emit_raw_row,
        row_pre_filter=trace_pre_filter,
    )

    manifest = build_manifest_payload(
        source_checksum=source_checksum,
        quality_output=result.quality_output,
        issues=list(issues),
        duckdb_version=get_duckdb_version(conn),
        normalized_path=normalized_path,
        trace_path=trace_path,
        manifest_path=manifest_path,
    )
    write_manifest(manifest_path, manifest)

    return StagedArtifacts(
        normalized_path=normalized_path,
        manifest_path=manifest_path,
        trace_path=trace_path,
    )
