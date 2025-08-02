"""Artifact materialization strategies: overlapped (background) and staged."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Any

from duckdb import DuckDBPyConnection

from normalize.core.engine.background import write_parquets_background
from normalize.stages.artifact_materialization import ArtifactMaterializationStage
from normalize.stages.artifact_materialization.constants import AUDIT_OUTPUT_COLUMNS
from normalize.stages.artifact_materialization.export import build_export_columns
from normalize.stages.artifact_materialization.manifest import (
    build_issue_summary,
    build_manifest_payload,
    write_manifest,
)
from normalize.utils.checksums import sha256_file
from shared.db.sql import read_columns


def start_overlapped_write(
    conn: DuckDBPyConnection,
    *,
    db_path: str,
    output_root: Path,
    fingerprint: str,
    trace_mode: str,
) -> tuple[ThreadPoolExecutor, Future[dict[str, float]]]:
    """Start background parquet write and return (pool, future)."""
    table_columns = read_columns(conn, "raw_input")
    export_columns = build_export_columns(table_columns)
    data_columns = [c for c in export_columns if c not in AUDIT_OUTPUT_COLUMNS]
    output_root.mkdir(parents=True, exist_ok=True)

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        write_parquets_background,
        db_path,
        output_root,
        fingerprint,
        trace_mode,
        "raw_input",
        export_columns,
        data_columns,
        table_columns,
    )
    return pool, future


def collect_overlapped_artifacts(
    write_future: Future[dict[str, float]],
    _artifact_pool: ThreadPoolExecutor,
    *,
    output_root: Path,
    fingerprint: str,
    stage_metrics: dict[str, dict[str, Any]],
    quality_summary: dict[str, Any],
    issue_dicts: list[dict[str, Any]],
    replay_config: dict[str, Any],
    effective_rules_version: str,
    source_checksum: str,
    duckdb_version: str,
    normalized_rows: int,
    data_column_count: int,
    trace_mode: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Wait for background write, compute checksums, and write manifest."""
    artifact_start = perf_counter()
    write_timing = write_future.result()

    normalized_path = output_root / f"{fingerprint}.parquet"
    trace_path = output_root / f"{fingerprint}.trace.parquet"
    manifest_path = output_root / f"{fingerprint}.manifest.json"

    section_start = perf_counter()
    normalized_checksum = sha256_file(normalized_path)
    trace_checksum = sha256_file(trace_path)
    checksum_seconds = perf_counter() - section_start

    issue_summary = build_issue_summary(issue_dicts)

    section_start = perf_counter()
    manifest = build_manifest_payload(
        fingerprint=fingerprint,
        source_checksums={"source_file": source_checksum},
        stage_metrics=stage_metrics,
        quality_summary=quality_summary,
        issue_summary=issue_summary,
        normalized_checksum=normalized_checksum,
        trace_checksum=trace_checksum,
        effective_config=replay_config,
        rules_version=effective_rules_version,
        duckdb_version=duckdb_version,
        normalized_path=normalized_path,
        trace_path=trace_path,
        manifest_path=manifest_path,
    )
    write_manifest(manifest_path, manifest)
    manifest_seconds = perf_counter() - section_start

    artifact_duration = perf_counter() - artifact_start
    artifact_metrics: dict[str, Any] = {
        "duration_seconds": artifact_duration,
        "normalized_rows": normalized_rows,
        "trace_rows": normalized_rows * data_column_count,
        "trace_mode": trace_mode,
        "normalized_path": str(normalized_path),
        "trace_path": str(trace_path),
        "manifest_path": str(manifest_path),
        "checksum_seconds": checksum_seconds,
        "manifest_write_seconds": manifest_seconds,
        **write_timing,
    }
    artifacts = {
        "normalized_parquet": str(normalized_path),
        "manifest_json": str(manifest_path),
        "trace_parquet": str(trace_path),
    }
    return artifacts, artifact_metrics


def run_staged_artifacts(
    conn: DuckDBPyConnection,
    *,
    output_root: Path,
    fingerprint: str,
    trace_mode: str,
    source_checksum: str,
    stage_metrics: dict[str, dict[str, Any]],
    quality_summary: dict[str, Any],
    issues: list[Any],
    replay_config: dict[str, Any],
    rules_version: str,
) -> tuple[dict[str, str], float]:
    """Sequential artifact write via ArtifactMaterializationStage. Returns (artifacts, duration)."""
    artifact_stage = ArtifactMaterializationStage()
    artifacts = artifact_stage.execute(
        conn,
        output_dir=output_root,
        fingerprint=fingerprint,
        trace_mode=trace_mode,
        source_checksums={"source_file": source_checksum},
        stage_metrics=stage_metrics,
        quality_summary=quality_summary,
        issues=issues,
        effective_config=replay_config,
        rules_version=rules_version,
    )
    duration = float(artifact_stage.metrics.get("duration_seconds", 0.0))
    return artifacts, duration
