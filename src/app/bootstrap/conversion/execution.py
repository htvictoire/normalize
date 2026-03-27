"""Conversion pipeline execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from shared.db.column_index import resolve_column_config_by_canonical
from shared.db.duckdb import DuckDBManager, resolve_db_path
from shared.db.sql import read_columns
from shared.ingestion import (
    IngestionRequest,
    cleanup_ingestion_setup,
    resolve_ingestion_setup,
    run_ingestion,
)
from shared.ingestion.canonicalization import HeaderCanonicalizationStage
from shared.models.column import ColumnConfig
from shared.models.issues import NormalizationIssue
from shared.models.normalization import ArtifactPaths, QualityOutput, SourceChecksums
from shared.models.operation import OperationConfig, SourceFormat
from shared.models.source import SourceRef

from app.bootstrap.conversion.replay import build_replay_config

from conversion.core.fingerprint import compute_fingerprint
from conversion.core.transform import execute_combined_transform
from conversion.stages.artifact_materialization import ArtifactMaterializationStage
from conversion.stages.cell_normalization import CellNormalizationStage
from conversion.stages.quality_metrics.stage import QualityMetricsStage
from conversion.stages.row_normalization import RowNormalizationStage


@dataclass(frozen=True)
class ConversionExecutionOutput:
    """Result payload from conversion pipeline execution."""

    status: str
    fingerprint: str
    quality_output: QualityOutput
    artifacts: ArtifactPaths


_RULES_VERSION = "v1"


def execute_conversion(
    source: SourceRef,
    source_format: SourceFormat,
    source_checksum: str,
    confirmed_column_config: dict[str, ColumnConfig],
    operation_config: OperationConfig,
    profiling_issues: list[NormalizationIssue],
    output_root: str | Path,
    run_id: str | None,
    duckdb_memory_limit: str,
    persisted_db_path: Path,
) -> ConversionExecutionOutput:
    """Run deterministic conversion pipeline and return artifact payload.

    If persisted_db_path exists (written by profiling), it is opened directly
    and ingestion + header canonicalization are skipped. Otherwise falls back
    to a fresh ingest from source.
    """
    use_cache = persisted_db_path.exists()

    if use_cache:
        db_arg = resolve_db_path(str(persisted_db_path))
        setup = None
    else:
        setup = resolve_ingestion_setup(source, source_format)
        db_arg = ":memory:"

    try:
        with DuckDBManager(memory_limit=duckdb_memory_limit, threads=4, database=db_arg) as conn:
            if not use_cache:
                run_ingestion(
                    IngestionRequest(
                        conn=conn,
                        source_url=setup.url,  # type: ignore[union-attr]
                        source_type=setup.source_type,  # type: ignore[union-attr]
                        source_format=source_format,
                    )
                )
                HeaderCanonicalizationStage().execute(conn)

            raw_columns = read_columns(conn)
            resolved_column_config = resolve_column_config_by_canonical(
                data_columns=raw_columns,
                column_config=confirmed_column_config,
            )

            row_plan = RowNormalizationStage(
                assign_indices=operation_config.assign_indices,
                drop_empty_rows=operation_config.drop_empty_rows,
            ).plan(conn, columns=raw_columns)

            cell_plan = CellNormalizationStage().plan(
                column_config=resolved_column_config,
                null_tokens=list(operation_config.null_tokens),
                columns=raw_columns,
                full_raw_row=operation_config.full_raw_row,
                emit_raw_row=operation_config.emit_raw_row,
                emit_parse_issues=operation_config.emit_parse_issues,
            )

            execute_combined_transform(conn, row_plan, cell_plan)

            quality_output = QualityMetricsStage().execute(
                conn,
                cell_plan.data_columns,
            )

            version_row = cast("tuple[object, ...]", conn.execute("SELECT version()").fetchone())
            duckdb_version = str(version_row[0])
            replay_config = build_replay_config(
                source_format,
                operation_config,
                resolved_column_config,
            )
            config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
            fingerprint = compute_fingerprint(
                source_checksum,
                config_json,
                _RULES_VERSION,
                duckdb_version,
            )

            artifacts = ArtifactMaterializationStage().execute(
                conn,
                output_dir=output_root,
                output_type=source.source_type,
                fingerprint=fingerprint,
                trace_mode=operation_config.trace_mode,
                source_checksums=SourceChecksums(source_file=source_checksum),
                quality_output=quality_output,
                issues=profiling_issues,
                effective_config=replay_config,
                run_id=run_id,
                rules_version=_RULES_VERSION,
            )
            return ConversionExecutionOutput(
                status="READY",
                fingerprint=fingerprint,
                quality_output=quality_output,
                artifacts=artifacts,
            )
    finally:
        if setup is not None:
            cleanup_ingestion_setup(setup)
