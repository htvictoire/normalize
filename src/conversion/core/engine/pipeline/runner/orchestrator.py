"""Pipeline execution for engine PROFILE/APPLY modes."""

from __future__ import annotations

import json
from pathlib import Path

from conversion.core.engine.config import EngineConfig
from conversion.core.engine.pipeline.replay import build_replay_config
from conversion.core.engine.pipeline.runner.config_resolution import (
    resolve_column_config_by_canonical,
)
from conversion.core.fingerprint import compute_fingerprint
from conversion.core.transform import execute_combined_transform
from conversion.stages.artifact_materialization import ArtifactMaterializationStage
from conversion.stages.cell_normalization import CellNormalizationStage
from conversion.stages.header_canonicalization import HeaderCanonicalizationStage
from conversion.stages.quality_metrics.stage import QualityMetricsStage
from conversion.stages.row_normalization import RowNormalizationStage
from shared.db.duckdb import DuckDBManager, resolve_db_path
from shared.db.sql import read_columns
from shared.ingestion import HeaderMode, IngestionStage
from shared.ingestion.checksum import sha256_stream
from shared.models.normalization import ArtifactPaths, NormalizationOutput, SourceChecksums
from shared.models.operation import CsvSourceFormat


def run_pipeline(
    *,
    source_csv: Path,
    output_root: Path,
    effective: EngineConfig,
    run_mode: str,
    duckdb_memory_limit: str,
) -> NormalizationOutput:
    """Execute deterministic conversion stages and optionally materialize artifacts."""
    null_tokens = list(effective.null_tokens)

    db_path = resolve_db_path(effective.duckdb_path)

    with DuckDBManager(
        memory_limit=duckdb_memory_limit,
        threads=effective.threads,
        database=db_path,
    ) as conn:
        IngestionStage().execute(
            conn,
            str(source_csv),
            source_type="local",
            source_format=CsvSourceFormat(
                encoding=effective.encoding,
                delimiter=effective.delimiter,
                header_mode=(
                    "present" if effective.header_mode is HeaderMode.PRESENT else "absent"
                ),
                header_row_index=effective.header_row_index,
            ),
        )

        HeaderCanonicalizationStage().execute(conn)

        raw_columns = read_columns(conn, "raw_input")
        resolved_column_config = resolve_column_config_by_canonical(
            data_columns=raw_columns,
            column_config=effective.column_config,
        )

        row_plan = RowNormalizationStage(
            assign_indices=effective.assign_indices,
            drop_empty_rows=effective.drop_empty_rows,
        ).plan(conn)

        cell_plan = CellNormalizationStage().plan(
            conn,
            column_config=resolved_column_config,
            full_raw_row=effective.full_raw_row,
            emit_raw_row=effective.emit_raw_row,
            emit_parse_issues=effective.emit_parse_issues,
            null_tokens=null_tokens,
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
        replay_config = build_replay_config(effective)
        config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
        source_checksum = sha256_stream(source_csv)
        fingerprint = compute_fingerprint(
            source_checksum,
            config_json,
            effective.rules_version,
            duckdb_version,
        )

        artifacts: ArtifactPaths | None = None
        if run_mode == "APPLY":
            artifacts = ArtifactMaterializationStage().execute(
                conn,
                output_dir=output_root,
                fingerprint=fingerprint,
                trace_mode=effective.trace_mode,
                source_checksums=SourceChecksums(source_file=source_checksum),
                quality_output=quality_output,
                issues=[],
                effective_config=replay_config,
                rules_version=effective.rules_version,
            )

    return NormalizationOutput(
        fingerprint=fingerprint,
        quality_output=quality_output,
        artifacts=artifacts,
    )
