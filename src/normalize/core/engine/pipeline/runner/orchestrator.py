"""Pipeline execution for engine PROFILE/APPLY modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from normalize.core.engine.config import EngineConfig
from normalize.core.engine.pipeline.replay import build_replay_config
from normalize.core.engine.pipeline.runner.config_resolution import (
    resolve_column_config_by_canonical,
)
from normalize.core.fingerprint import compute_fingerprint
from normalize.core.transform import execute_combined_transform
from normalize.stages.artifact_materialization import ArtifactMaterializationStage
from normalize.stages.cell_normalization import CellNormalizationStage
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from normalize.stages.row_normalization import RowNormalizationStage
from shared.db.duckdb import DuckDBManager, resolve_db_path
from shared.db.sql import read_columns
from shared.ingestion import IngestionStage


def run_pipeline(
    *,
    source_csv: Path,
    output_root: Path,
    effective: EngineConfig,
    run_mode: str,
    duckdb_memory_limit: str,
) -> dict[str, Any]:
    """Execute deterministic conversion stages and optionally materialize artifacts."""
    token_kwargs = {
        "null_tokens": list(effective.null_tokens),
        "boolean_true_tokens": list(effective.boolean_true_tokens),
        "boolean_false_tokens": list(effective.boolean_false_tokens),
    }

    db_path = resolve_db_path(effective.duckdb_path)

    with DuckDBManager(
        memory_limit=duckdb_memory_limit,
        threads=effective.threads,
        database=db_path,
    ) as conn:
        ingestion_result = IngestionStage().execute(
            conn,
            source_csv,
            header_mode=effective.header_mode,
            header_row_index=effective.header_row_index,
            encoding=effective.encoding,
            delimiter=effective.delimiter,
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
            null_tokens=token_kwargs["null_tokens"],
            boolean_true_tokens=token_kwargs["boolean_true_tokens"],
            boolean_false_tokens=token_kwargs["boolean_false_tokens"],
        )

        execute_combined_transform(conn, row_plan, cell_plan)

        duckdb_version_row = conn.execute("SELECT version()").fetchone()
        if duckdb_version_row is None:
            raise RuntimeError("duckdb version query returned no rows")
        duckdb_version = str(duckdb_version_row[0])
        replay_config = build_replay_config(effective)
        config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
        fingerprint = compute_fingerprint(
            ingestion_result.file_checksum,
            config_json,
            effective.rules_version,
            duckdb_version,
        )

        artifacts: dict[str, str] | None = None
        if run_mode == "APPLY":
            artifacts = ArtifactMaterializationStage().execute(
                conn,
                output_dir=output_root,
                fingerprint=fingerprint,
                trace_mode=effective.trace_mode,
                source_checksums={"source_file": ingestion_result.file_checksum},
                stage_metrics={},
                quality_summary={},
                issues=[],
                effective_config=replay_config,
                rules_version=effective.rules_version,
            )

    return {
        "status": "READY",
        "fingerprint": fingerprint,
        "artifacts": artifacts if run_mode == "APPLY" else None,
    }
