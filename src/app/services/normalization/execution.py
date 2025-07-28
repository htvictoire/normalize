"""Normalization pipeline execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.instance import InstanceModel
from app.services.normalization.profiling import profiling_stats_by_canonical
from app.services.normalization.replay import build_instance_replay_config
from normalize.core.engine.issues import build_issues, issue_to_dict
from normalize.core.engine.pipeline.currency import collect_currency_analysis
from normalize.core.engine.pipeline.runner import resolve_column_config_by_canonical
from normalize.core.fingerprint import compute_fingerprint
from normalize.core.quality import compute_quality_score
from normalize.core.transform import execute_combined_transform
from normalize.stages.artifact_materialization import ArtifactMaterializationStage
from normalize.stages.cell_normalization import CellNormalizationStage
from normalize.stages.decision_evaluation import DecisionEvaluationStage, DecisionPolicy
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from normalize.stages.quality_metrics import QualityMetricsStage
from normalize.stages.row_normalization import RowNormalizationStage
from shared.db.duckdb import DuckDBManager
from shared.db.sql import read_columns
from shared.ingestion import HeaderMode, IngestionRequest, run_ingestion
from shared.models.operation import RunMode
from shared.utils.column_positions import build_position_to_name


def execute_normalization(
    instance: InstanceModel,
    *,
    output_root: Path,
    run_mode: RunMode,
    rules_version: str,
    duckdb_memory_limit: str,
) -> dict[str, Any]:
    """Run the full normalization pipeline and return a result dict."""
    operation = instance.operation_config
    confirmed_column_config = instance.confirmed_column_config
    profiling_stats = instance.profiling_stats
    source_csv = Path(instance.source_r2_url)

    stage_metrics: dict[str, float] = {}
    artifacts: dict[str, str] | None = None

    with DuckDBManager(memory_limit=duckdb_memory_limit, threads=4) as conn:
        ingestion_result = run_ingestion(
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
        stage_metrics["ingestion"] = ingestion_result.duration_seconds

        header = HeaderCanonicalizationStage()
        header.execute(conn)
        stage_metrics["header_canonicalization"] = float(
            header.metrics.get("duration_seconds", 0.0)
        )

        raw_columns = read_columns(conn, "raw_input")
        position_to_canonical = build_position_to_name(raw_columns)
        resolved_column_config = resolve_column_config_by_canonical(
            data_columns=raw_columns,
            column_config=confirmed_column_config,
        )

        row_norm = RowNormalizationStage(
            assign_indices=operation.assign_indices,
            drop_empty_rows=operation.drop_empty_rows,
        )
        row_plan = row_norm.plan(conn)

        cell_norm = CellNormalizationStage()
        cell_plan = cell_norm.plan(
            conn,
            column_config=resolved_column_config,
            null_tokens=list(operation.null_tokens),
            boolean_true_tokens=list(operation.boolean_true_tokens),
            boolean_false_tokens=list(operation.boolean_false_tokens),
            full_raw_row=operation.full_raw_row,
            emit_raw_row=operation.emit_raw_row,
            emit_parse_issues=operation.emit_parse_issues,
        )

        transform_result = execute_combined_transform(conn, row_plan, cell_plan)
        stage_metrics["combined_transform"] = float(transform_result["duration_seconds"])

        total_parse_error_cells = int(
            conn.execute("SELECT COALESCE(SUM(_parse_error_count), 0) FROM raw_input")
            .fetchone()[0]
        )

        quality = QualityMetricsStage()
        quality_result = quality.execute(
            conn,
            row_count=profiling_stats.row_count,
            per_column_stats=profiling_stats_by_canonical(
                position_to_canonical=position_to_canonical,
                profiling_stats=profiling_stats,
            ),
            total_parse_error_cells=total_parse_error_cells,
            include_unique_ratio=operation.include_unique_ratio,
            include_per_column_parse_error_counts=(
                operation.include_per_column_parse_error_counts
            ),
            approximate_unique=operation.approximate_unique,
        )
        stage_metrics["quality_metrics"] = float(quality.metrics.get("duration_seconds", 0.0))

        currency_analysis = collect_currency_analysis(
            conn,
            column_config=resolved_column_config,
            null_tokens=tuple(operation.null_tokens),
        )
        pattern_consistency_ratio = currency_analysis["pattern_consistency_ratio"]
        currency_issues = currency_analysis["issues"]

        quality_score = compute_quality_score(
            float(quality_result["parse_success_ratio"]),
            float(quality_result["completeness_ratio"]),
            pattern_consistency_ratio=pattern_consistency_ratio,
        )
        issues = [*currency_issues, *build_issues(quality_result)]
        decision = DecisionEvaluationStage(
            policy=DecisionPolicy.from_inputs(
                ready_threshold=operation.decision_thresholds.ready,
                warning_threshold=operation.decision_thresholds.warning,
            )
        )
        status = decision.execute(quality_score, issues)
        stage_metrics["decision_evaluation"] = float(
            decision.metrics.get("duration_seconds", 0.0)
        )

        duckdb_version = str(conn.execute("SELECT version()").fetchone()[0])
        replay_config = build_instance_replay_config(instance, resolved_column_config)
        config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
        fingerprint = compute_fingerprint(
            instance.source_checksum,
            config_json,
            rules_version,
            duckdb_version,
        )

        if run_mode == "APPLY":
            artifact_stage = ArtifactMaterializationStage()
            artifacts = artifact_stage.execute(
                conn,
                output_dir=output_root,
                fingerprint=fingerprint,
                trace_mode=operation.trace_mode,
                source_checksums={"source_file": instance.source_checksum},
                stage_metrics={
                    name: {"duration_seconds": seconds}
                    for name, seconds in stage_metrics.items()
                },
                quality_summary={
                    "quality_score": float(quality_score),
                    "parse_success_ratio": quality_result["parse_success_ratio"],
                    "completeness_ratio": quality_result["completeness_ratio"],
                    "pattern_consistency_ratio": pattern_consistency_ratio,
                    "row_count": quality_result["row_count"],
                    "total_parse_error_cells": quality_result["total_parse_error_cells"],
                    "total_nullish_cells": quality_result["total_nullish_cells"],
                },
                issues=[issue_to_dict(issue) for issue in issues],
                effective_config=replay_config,
                rules_version=rules_version,
            )
            stage_metrics["artifact_materialization"] = float(
                artifact_stage.metrics.get("duration_seconds", 0.0)
            )

    return {
        "status": status.value,
        "quality_score": float(quality_score),
        "issues": [issue_to_dict(issue) for issue in issues],
        "fingerprint": fingerprint,
        "artifacts": artifacts,
        "stage_metrics": dict(stage_metrics),
        "total_parse_error_cells": total_parse_error_cells,
    }
