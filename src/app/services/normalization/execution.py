"""Normalization pipeline execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.instance import InstanceModel
from app.services.normalization.replay import build_instance_replay_config
from normalize.core.engine.pipeline.runner import resolve_column_config_by_canonical
from normalize.core.fingerprint import compute_fingerprint
from normalize.core.transform import execute_combined_transform
from normalize.stages.artifact_materialization import ArtifactMaterializationStage
from normalize.stages.cell_normalization import CellNormalizationStage
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from normalize.stages.row_normalization import RowNormalizationStage
from shared.db.duckdb import DuckDBManager
from shared.db.sql import read_columns
from shared.ingestion import HeaderMode, IngestionRequest, run_ingestion
from shared.models.operation import RunMode


def execute_normalization(
    instance: InstanceModel,
    *,
    output_root: Path,
    run_mode: RunMode,
    rules_version: str,
    duckdb_memory_limit: str,
) -> dict[str, Any]:
    """Run deterministic conversion pipeline and return artifact payload."""
    operation = instance.operation_config
    confirmed_column_config = instance.confirmed_column_config
    if operation is None or confirmed_column_config is None:
        raise ValueError("instance is missing confirmed config")

    source_csv = Path(instance.source_r2_url)

    with DuckDBManager(memory_limit=duckdb_memory_limit, threads=4) as conn:
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=source_csv,
                table_name="raw_input",
                header_mode=HeaderMode(instance.source_format.header_mode),
                header_row_index=instance.source_format.header_row_index,
                encoding=instance.source_format.encoding,
                delimiter=instance.source_format.delimiter,
            )
        )

        HeaderCanonicalizationStage().execute(conn)

        raw_columns = read_columns(conn, "raw_input")
        resolved_column_config = resolve_column_config_by_canonical(
            data_columns=raw_columns,
            column_config=confirmed_column_config,
        )

        row_plan = RowNormalizationStage(
            assign_indices=operation.assign_indices,
            drop_empty_rows=operation.drop_empty_rows,
        ).plan(conn)

        cell_plan = CellNormalizationStage().plan(
            conn,
            column_config=resolved_column_config,
            null_tokens=list(operation.null_tokens),
            boolean_true_tokens=list(operation.boolean_true_tokens),
            boolean_false_tokens=list(operation.boolean_false_tokens),
            full_raw_row=operation.full_raw_row,
            emit_raw_row=operation.emit_raw_row,
            emit_parse_issues=operation.emit_parse_issues,
        )

        execute_combined_transform(conn, row_plan, cell_plan)

        duckdb_version_row = conn.execute("SELECT version()").fetchone()
        if duckdb_version_row is None:
            raise RuntimeError("duckdb version query returned no rows")
        duckdb_version = str(duckdb_version_row[0])
        replay_config = build_instance_replay_config(instance, resolved_column_config)
        config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
        source_checksum = instance.source_checksum
        if source_checksum is None:
            raise ValueError("instance is missing source checksum")
        fingerprint = compute_fingerprint(
            source_checksum,
            config_json,
            rules_version,
            duckdb_version,
        )

        artifacts: dict[str, str] | None = None
        if run_mode == "APPLY":
            profile_issues = []
            if instance.profile_output is not None:
                for issue in instance.profile_output.issues:
                    profile_issues.append(
                        {
                            "code": issue.code,
                            "severity": str(issue.severity.value),
                            "message": issue.message,
                            "location": issue.location,
                            "evidence": issue.evidence,
                            "pattern_context": issue.pattern_context,
                        }
                    )

            artifacts = ArtifactMaterializationStage().execute(
                conn,
                output_dir=output_root,
                fingerprint=fingerprint,
                trace_mode=operation.trace_mode,
                source_checksums={"source_file": source_checksum},
                stage_metrics={},
                quality_summary={},
                issues=profile_issues,
                effective_config=replay_config,
                rules_version=rules_version,
            )

    return {
        "status": "READY",
        "fingerprint": fingerprint,
        "artifacts": artifacts,
    }
