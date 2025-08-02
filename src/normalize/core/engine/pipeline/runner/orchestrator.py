"""Pipeline execution for engine PROFILE/APPLY modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from normalize.core.engine.config import EngineConfig
from normalize.core.engine.issues import build_issues, issue_to_dict
from normalize.core.engine.pipeline.currency import collect_currency_analysis
from normalize.core.engine.pipeline.replay import build_replay_config
from normalize.core.engine.pipeline.runner.artifacts import (
    collect_overlapped_artifacts,
    run_staged_artifacts,
    start_overlapped_write,
)
from normalize.core.engine.pipeline.runner.config_resolution import (
    resolve_column_config_by_canonical,
)
from normalize.core.fingerprint import compute_fingerprint
from normalize.core.quality import compute_quality_score
from normalize.core.token_policy import TokenPolicy
from normalize.core.transform import execute_combined_transform
from normalize.stages.cell_normalization import CellNormalizationStage
from normalize.stages.decision_evaluation import DecisionEvaluationStage, DecisionPolicy
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from normalize.stages.quality_metrics import QualityMetricsStage
from normalize.stages.quality_metrics.queries import (
    read_column_null_stats,
    read_total_parse_error_cells,
)
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
    """Execute stage sequence and return engine result payload."""
    stage_seconds: dict[str, float] = {}
    stage_metrics: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, str] | None = None

    token_kwargs = {
        "null_tokens": list(effective.null_tokens),
        "boolean_true_tokens": list(effective.boolean_true_tokens),
        "boolean_false_tokens": list(effective.boolean_false_tokens),
    }

    token_policy = TokenPolicy.from_user_inputs(
        null_tokens=token_kwargs["null_tokens"],
        boolean_true_tokens=token_kwargs["boolean_true_tokens"],
        boolean_false_tokens=token_kwargs["boolean_false_tokens"],
    )

    db_path = resolve_db_path(effective.duckdb_path)

    with DuckDBManager(
        memory_limit=duckdb_memory_limit,
        threads=effective.threads,
        database=db_path,
    ) as conn:
        ingestion = IngestionStage()
        ingestion_result = ingestion.execute(
            conn,
            source_csv,
            header_mode=effective.header_mode,
            header_row_index=effective.header_row_index,
            encoding=effective.encoding,
            delimiter=effective.delimiter,
        )
        stage_seconds["ingestion"] = float(ingestion.metrics.get("duration_seconds", 0.0))
        stage_metrics["ingestion"] = dict(ingestion.metrics)

        header = HeaderCanonicalizationStage()
        header.execute(conn)
        stage_seconds["header_canonicalization"] = float(
            header.metrics.get("duration_seconds", 0.0)
        )
        stage_metrics["header_canonicalization"] = dict(header.metrics)

        raw_columns = read_columns(conn, "raw_input")
        resolved_column_config = resolve_column_config_by_canonical(
            data_columns=raw_columns,
            column_config=effective.column_config,
        )

        currency_analysis = collect_currency_analysis(
            conn,
            column_config=resolved_column_config,
            null_tokens=token_policy.null_tokens,
        )
        pattern_consistency_ratio = currency_analysis["pattern_consistency_ratio"]
        currency_issues = currency_analysis["issues"]

        row_norm = RowNormalizationStage(
            assign_indices=effective.assign_indices,
            drop_empty_rows=effective.drop_empty_rows,
        )
        row_plan = row_norm.plan(conn)

        cell_norm = CellNormalizationStage()
        cell_plan = cell_norm.plan(
            conn,
            column_config=resolved_column_config,
            full_raw_row=effective.full_raw_row,
            emit_raw_row=effective.emit_raw_row,
            emit_parse_issues=effective.emit_parse_issues,
            **token_kwargs,
        )

        transform_result = execute_combined_transform(conn, row_plan, cell_plan)
        stage_seconds["combined_transform"] = float(transform_result["duration_seconds"])
        stage_metrics["combined_transform"] = {str(k): v for k, v in transform_result.items()}

        duckdb_version = str(conn.execute("SELECT version()").fetchone()[0])
        replay_config = build_replay_config(effective)
        config_json = json.dumps(replay_config, sort_keys=True, separators=(",", ":"))
        fingerprint = compute_fingerprint(
            ingestion_result.file_checksum,
            config_json,
            effective.rules_version,
            duckdb_version,
        )

        use_overlapped_artifacts = run_mode == "APPLY" and db_path != ":memory:"
        write_future = None
        artifact_pool = None

        if use_overlapped_artifacts:
            artifact_pool, write_future = start_overlapped_write(
                conn,
                db_path=db_path,
                output_root=output_root,
                fingerprint=fingerprint,
                trace_mode=effective.trace_mode,
            )

        try:
            data_columns = list(cell_plan.data_columns)
            row_count = int(transform_result["rows_after"])
            per_column_stats = read_column_null_stats(
                conn,
                table_name="raw_input",
                columns=data_columns,
            )
            total_parse_error_cells = read_total_parse_error_cells(
                conn,
                table_name="raw_input",
                columns=data_columns,
            )

            quality = QualityMetricsStage()
            quality_result = quality.execute(
                conn,
                row_count=row_count,
                per_column_stats=per_column_stats,
                total_parse_error_cells=total_parse_error_cells,
                include_unique_ratio=effective.include_unique_ratio,
                include_per_column_parse_error_counts=effective.include_per_column_parse_error_counts,
                approximate_unique=effective.approximate_unique,
            )
            stage_seconds["quality_metrics"] = float(quality.metrics.get("duration_seconds", 0.0))
            stage_metrics["quality_metrics"] = dict(quality.metrics)

            quality_score = compute_quality_score(
                float(quality_result["parse_success_ratio"]),
                float(quality_result["completeness_ratio"]),
                pattern_consistency_ratio=pattern_consistency_ratio,
            )
            issues = [*currency_issues, *build_issues(quality_result)]
            decision_policy = DecisionPolicy.from_inputs(
                ready_threshold=effective.decision_ready_threshold,
                warning_threshold=effective.decision_warning_threshold,
            )
            decision = DecisionEvaluationStage(policy=decision_policy)
            status = decision.execute(quality_score, issues)
            stage_seconds["decision_evaluation"] = float(
                decision.metrics.get("duration_seconds", 0.0)
            )
            stage_metrics["decision_evaluation"] = dict(decision.metrics)

            issue_dicts = [issue_to_dict(issue) for issue in issues]
            quality_summary = {
                "quality_score": float(quality_score),
                "parse_success_ratio": quality_result["parse_success_ratio"],
                "completeness_ratio": quality_result["completeness_ratio"],
                "pattern_consistency_ratio": pattern_consistency_ratio,
                "row_count": quality_result["row_count"],
                "total_parse_error_cells": quality_result["total_parse_error_cells"],
                "total_nullish_cells": quality_result["total_nullish_cells"],
            }

            if write_future is not None:
                artifacts, artifact_metrics = collect_overlapped_artifacts(
                    write_future,
                    artifact_pool,
                    output_root=output_root,
                    fingerprint=fingerprint,
                    stage_metrics=stage_metrics,
                    quality_summary=quality_summary,
                    issue_dicts=issue_dicts,
                    replay_config=replay_config,
                    effective_rules_version=effective.rules_version,
                    source_checksum=ingestion_result.file_checksum,
                    duckdb_version=duckdb_version,
                    normalized_rows=int(quality_result["row_count"]),
                    data_column_count=len(data_columns),
                    trace_mode=effective.trace_mode,
                )
                stage_seconds["artifact_materialization"] = artifact_metrics["duration_seconds"]
                stage_metrics["artifact_materialization"] = artifact_metrics

            elif run_mode == "APPLY":
                artifacts, artifact_duration = run_staged_artifacts(
                    conn,
                    output_root=output_root,
                    fingerprint=fingerprint,
                    trace_mode=effective.trace_mode,
                    source_checksum=ingestion_result.file_checksum,
                    stage_metrics=stage_metrics,
                    quality_summary=quality_summary,
                    issues=issue_dicts,
                    replay_config=replay_config,
                    rules_version=effective.rules_version,
                )
                stage_seconds["artifact_materialization"] = artifact_duration
                stage_metrics["artifact_materialization"] = dict(
                    quality.metrics
                )  # reuse last metrics dict as placeholder

        finally:
            if artifact_pool is not None:
                artifact_pool.shutdown(wait=True)

    return {
        "status": status.value,
        "quality_score": float(quality_score),
        "issues": issue_dicts,
        "fingerprint": fingerprint,
        "artifacts": artifacts if run_mode == "APPLY" else None,
        "stage_seconds": stage_seconds,
    }
