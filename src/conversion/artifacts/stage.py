"""Artifact materialization."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.models.issues import NormalizationIssue
from shared.models.normalization import ArtifactPaths
from shared.models.operation import FileSource, TraceMode

from conversion.artifacts.publish import build_artifact_publisher
from conversion.artifacts.staging import stage_artifacts
from conversion.models import TransformResult


def materialize_artifacts(
    conn: DuckDBPyConnection,
    output_dir: str | Path,
    output_type: FileSource,
    result: TransformResult,
    source_checksum: str,
    issues: Sequence[NormalizationIssue],
    run_id: str,
    trace_mode: TraceMode,
    full_raw_row: bool,
) -> ArtifactPaths:
    """Stages and publishes the normalized Parquet, manifest, and trace to local disk or S3."""

    publisher = build_artifact_publisher(
        output_type=output_type,
        output_root=output_dir,
        run_id=run_id,
    )
    with publisher.staging_root() as staging_root:
        staged = stage_artifacts(
            conn,
            output_root=staging_root,
            result=result,
            source_checksum=source_checksum,
            issues=issues,
            trace_mode=trace_mode,
            full_raw_row=full_raw_row,
        )
        return publisher.publish(staged)
