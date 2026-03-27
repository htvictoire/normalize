"""Artifact materialization stage (Parquet + manifest + trace)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from duckdb import DuckDBPyConnection

from conversion.stages.artifact_materialization.bundle import stage_artifacts
from conversion.stages.artifact_materialization.publish import build_artifact_publisher
from shared.models.issues import NormalizationIssue
from shared.models.normalization import ArtifactPaths, QualityOutput, SourceChecksums
from shared.models.operation import FileSource
from shared.stage import Stage


class ArtifactMaterializationStage(Stage):
    """Materialize normalized artifacts and publish them to the selected backend."""

    def execute(
        self,
        conn: DuckDBPyConnection,
        *,
        output_dir: str | Path,
        output_type: FileSource,
        fingerprint: str,
        quality_output: QualityOutput,
        source_checksums: SourceChecksums,
        issues: Sequence[NormalizationIssue],
        effective_config: Mapping[str, Any],
        run_id: str | None = None,
        trace_mode: str = "full",
        stage_metrics: Mapping[str, Mapping[str, Any]] | None = None,
        rules_version: str = "v1",
    ) -> ArtifactPaths:
        """Write normalized parquet, trace parquet, and manifest JSON."""
        start_time = perf_counter()
        timing: dict[str, float] = {}
        if trace_mode not in {"full", "sparse"}:
            raise ValueError("trace_mode must be one of: full, sparse")

        publisher = build_artifact_publisher(
            output_type=output_type,
            output_root=output_dir,
            run_id=run_id,
        )
        with publisher.staging_root() as staging_root:
            staged = stage_artifacts(
                conn,
                output_root=staging_root,
                fingerprint=fingerprint,
                quality_output=quality_output,
                source_checksums=source_checksums,
                issues=issues,
                effective_config=effective_config,
                trace_mode=trace_mode,
                stage_metrics=stage_metrics,
                rules_version=rules_version,
                timing=timing,
            )
            artifact_paths = publisher.publish(staged)

        normalized_rows = quality_output.row_count
        trace_rows = normalized_rows * staged.data_column_count

        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "normalized_rows": normalized_rows,
            "trace_rows": trace_rows,
            "trace_mode": trace_mode,
            "normalized_path": artifact_paths.normalized_parquet,
            "trace_path": artifact_paths.trace_parquet,
            "manifest_path": artifact_paths.manifest_json,
            **timing,
        }
        return artifact_paths
