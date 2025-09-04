"""Conversion pipeline execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.bootstrap.conversion.replay import build_replay_config
from conversion.core.engine.pipeline.runner import resolve_column_config_by_canonical
from conversion.core.fingerprint import compute_fingerprint
from conversion.core.transform import execute_combined_transform
from conversion.stages.artifact_materialization import ArtifactMaterializationStage
from conversion.stages.cell_normalization import CellNormalizationStage
from conversion.stages.header_canonicalization import HeaderCanonicalizationStage
from conversion.stages.quality_metrics.stage import QualityMetricsStage
from conversion.stages.row_normalization import RowNormalizationStage
from shared.db.duckdb import DuckDBManager
from shared.db.sql import read_columns
from shared.ingestion import IngestionRequest, run_ingestion
from shared.models.column import ColumnConfig
from shared.models.issues import NormalizationIssue
from shared.models.normalization import ArtifactPaths, QualityOutput, SourceChecksums
from shared.models.operation import (
    CsvSourceFormat,
    ExcelSourceFormat,
    JsonSourceFormat,
    OperationConfig,
    RunMode,
)


@dataclass(frozen=True)
class ConversionExecutionOutput:
    """Result payload from conversion pipeline execution."""

    status: str
    fingerprint: str
    quality_output: QualityOutput
    artifacts: ArtifactPaths | None


def execute_conversion(
    *,
    source_path: Path,
    source_format: CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat,
    source_checksum: str,
    confirmed_column_config: dict[str, ColumnConfig],
    operation_config: OperationConfig,
    profiling_issues: list[NormalizationIssue],
    output_root: Path,
    run_mode: RunMode,
    rules_version: str,
    duckdb_memory_limit: str,
) -> ConversionExecutionOutput:
    """Run deterministic conversion pipeline and return artifact payload."""
    with DuckDBManager(memory_limit=duckdb_memory_limit, threads=4) as conn:
        run_ingestion(
            IngestionRequest(
                conn=conn,
                source_path=source_path,
                source_format=source_format,
                table_name="raw_input",
            )
        )

        HeaderCanonicalizationStage().execute(conn)

        raw_columns = read_columns(conn, "raw_input")
        resolved_column_config = resolve_column_config_by_canonical(
            data_columns=raw_columns,
            column_config=confirmed_column_config,
        )

        row_plan = RowNormalizationStage(
            assign_indices=operation_config.assign_indices,
            drop_empty_rows=operation_config.drop_empty_rows,
        ).plan(conn)

        cell_plan = CellNormalizationStage().plan(
            conn,
            column_config=resolved_column_config,
            null_tokens=list(operation_config.null_tokens),
            full_raw_row=operation_config.full_raw_row,
            emit_raw_row=operation_config.emit_raw_row,
            emit_parse_issues=operation_config.emit_parse_issues,
        )

        execute_combined_transform(conn, row_plan, cell_plan)

        quality_output = QualityMetricsStage().execute(
            conn,
            data_columns=cell_plan.data_columns,
        )

        duckdb_version_row = conn.execute("SELECT version()").fetchone()
        if duckdb_version_row is None:
            raise RuntimeError("duckdb version query returned no rows")
        duckdb_version = str(duckdb_version_row[0])
        replay_config = build_replay_config(
            source_format=source_format,
            operation_config=operation_config,
            confirmed_column_config=resolved_column_config,
        )
        config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
        fingerprint = compute_fingerprint(
            source_checksum,
            config_json,
            rules_version,
            duckdb_version,
        )

        artifacts: ArtifactPaths | None = None
        if run_mode == "APPLY":
            artifacts = ArtifactMaterializationStage().execute(
                conn,
                output_dir=output_root,
                fingerprint=fingerprint,
                trace_mode=operation_config.trace_mode,
                source_checksums=SourceChecksums(source_file=source_checksum),
                quality_output=quality_output,
                issues=profiling_issues,
                effective_config=replay_config,
                rules_version=rules_version,
            )

    return ConversionExecutionOutput(
        status="READY",
        fingerprint=fingerprint,
        quality_output=quality_output,
        artifacts=artifacts,
    )
