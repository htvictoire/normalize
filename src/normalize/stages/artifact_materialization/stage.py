"""Artifact materialization stage (Parquet + manifest + trace)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from duckdb import DuckDBPyConnection

from normalize.stages.artifact_materialization.constants import (
    AUDIT_OUTPUT_COLUMNS,
)
from normalize.stages.artifact_materialization.export import (
    build_export_columns,
    write_normalized_parquet,
)
from normalize.stages.artifact_materialization.manifest import (
    build_issue_summary,
    build_manifest_payload,
    write_manifest,
)
from normalize.stages.artifact_materialization.trace import write_trace_parquet
from normalize.utils.checksums import sha256_file
from shared.db.sql import read_columns, validate_identifier
from shared.stages.base import Stage


class ArtifactMaterializationStage(Stage):
    """Materialize normalized artifacts to local filesystem."""

    def execute(
        self,
        conn: DuckDBPyConnection,
        *,
        output_dir: str | Path,
        fingerprint: str,
        trace_mode: str = "full",
        table_name: str = "raw_input",
        source_checksums: Mapping[str, str] | None = None,
        stage_metrics: Mapping[str, Mapping[str, Any]] | None = None,
        quality_summary: Mapping[str, Any] | None = None,
        issues: Sequence[Mapping[str, Any]] | None = None,
        effective_config: Mapping[str, Any] | None = None,
        rules_version: str = "v1",
    ) -> dict[str, str]:
        """Write normalized parquet, trace parquet, and manifest JSON."""
        start_time = perf_counter()
        timing: dict[str, float] = {}
        validate_identifier(table_name)
        if trace_mode not in {"full", "sparse"}:
            raise ValueError("trace_mode must be one of: full, sparse")
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        normalized_path = output_root / f"{fingerprint}.parquet"
        manifest_path = output_root / f"{fingerprint}.manifest.json"
        trace_path = output_root / f"{fingerprint}.trace.parquet"

        # Build export column order
        section_start = perf_counter()
        table_columns = read_columns(conn, table_name)
        export_columns = build_export_columns(table_columns)
        data_columns = [col for col in export_columns if col not in AUDIT_OUTPUT_COLUMNS]
        timing["prepare_columns_seconds"] = perf_counter() - section_start

        # Write normalized parquet directly (no temp table)
        section_start = perf_counter()
        write_normalized_parquet(
            conn,
            normalized_path=normalized_path,
            table_name=table_name,
            export_columns=export_columns,
        )
        timing["write_normalized_parquet_seconds"] = perf_counter() - section_start

        # Write trace parquet
        section_start = perf_counter()
        # When sparse mode is active and _parse_error_count exists, pre-filter
        # rows before UNPIVOT to avoid materializing all cells.  This is sound
        # when _raw_row is conditional (full_raw_row=False) because _raw_row is
        # NULL for clean rows — meaning the sparse cell-level filter would
        # exclude them anyway.
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

        # Checksums
        section_start = perf_counter()
        normalized_checksum = sha256_file(normalized_path)
        trace_checksum = sha256_file(trace_path)
        timing["checksum_seconds"] = perf_counter() - section_start

        issue_summary = build_issue_summary(issues or ())
        section_start = perf_counter()
        duckdb_version = str(conn.execute("SELECT version()").fetchone()[0])
        timing["duckdb_version_read_seconds"] = perf_counter() - section_start

        # Row count from quality summary or query
        normalized_rows: int | None = None
        row_count_value = (
            (quality_summary or {}).get("row_count") if quality_summary is not None else None
        )
        if row_count_value is not None:
            try:
                normalized_rows = int(row_count_value)
            except (TypeError, ValueError):
                normalized_rows = None
        if normalized_rows is None:
            section_start = perf_counter()
            normalized_rows = int(
                conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
            timing["row_count_query_seconds"] = perf_counter() - section_start
        trace_rows = normalized_rows * len(data_columns)

        # Manifest
        section_start = perf_counter()
        manifest = build_manifest_payload(
            fingerprint=fingerprint,
            source_checksums=source_checksums,
            stage_metrics=stage_metrics,
            quality_summary=quality_summary,
            issue_summary=issue_summary,
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

        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "normalized_rows": normalized_rows,
            "trace_rows": trace_rows,
            "trace_mode": trace_mode,
            "normalized_path": str(normalized_path),
            "trace_path": str(trace_path),
            "manifest_path": str(manifest_path),
            **timing,
        }
        return {
            "normalized_parquet": str(normalized_path),
            "manifest_json": str(manifest_path),
            "trace_parquet": str(trace_path),
        }
