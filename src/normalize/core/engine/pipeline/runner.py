"""Pipeline execution for engine PROFILE/APPLY modes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Any

from normalize.core.column_config import ColumnConfig
from normalize.core.column_positions import build_position_to_name
from normalize.core.duckdb_manager import DuckDBManager, resolve_db_path
from normalize.core.engine.background import write_parquets_background
from normalize.core.engine.config import EngineConfig
from normalize.core.engine.issues import build_issues, issue_to_dict
from normalize.core.engine.pipeline.currency import collect_currency_analysis
from normalize.core.engine.pipeline.replay import build_replay_config
from normalize.core.fingerprint import compute_fingerprint
from normalize.core.quality import compute_quality_score
from normalize.core.sql_helpers import read_columns
from normalize.core.token_policy import TokenPolicy
from normalize.core.transform import execute_combined_transform
from normalize.stages.artifact_materialization import ArtifactMaterializationStage
from normalize.stages.artifact_materialization.constants import AUDIT_OUTPUT_COLUMNS
from normalize.stages.artifact_materialization.export import build_export_columns
from normalize.stages.artifact_materialization.manifest import (
    build_issue_summary,
    build_manifest_payload,
    write_manifest,
)
from normalize.stages.cell_normalization import CellNormalizationStage
from normalize.stages.decision_evaluation import DecisionEvaluationStage, DecisionPolicy
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage
from normalize.stages.ingestion import IngestionStage
from normalize.stages.quality_metrics import QualityMetricsStage
from normalize.stages.row_normalization import RowNormalizationStage
from normalize.utils.checksums import sha256_file


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
        write_future: Future[dict[str, float]] | None = None
        artifact_pool: ThreadPoolExecutor | None = None

        if use_overlapped_artifacts:
            table_columns = read_columns(conn, "raw_input")
            export_columns = build_export_columns(table_columns)
            data_columns = [c for c in export_columns if c not in AUDIT_OUTPUT_COLUMNS]
            output_root.mkdir(parents=True, exist_ok=True)

            artifact_pool = ThreadPoolExecutor(max_workers=1)
            write_future = artifact_pool.submit(
                write_parquets_background,
                db_path,
                output_root,
                fingerprint,
                effective.trace_mode,
                "raw_input",
                export_columns,
                data_columns,
                table_columns,
            )

        try:
            quality = QualityMetricsStage()
            quality_result = quality.execute(
                conn,
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

            if write_future is not None:
                artifact_start = perf_counter()
                write_timing = write_future.result()

                normalized_path = output_root / f"{fingerprint}.parquet"
                trace_path = output_root / f"{fingerprint}.trace.parquet"
                manifest_path = output_root / f"{fingerprint}.manifest.json"

                section_start = perf_counter()
                normalized_checksum = sha256_file(normalized_path)
                trace_checksum = sha256_file(trace_path)
                checksum_seconds = perf_counter() - section_start

                issue_dicts = [issue_to_dict(issue) for issue in issues]
                issue_summary = build_issue_summary(issue_dicts)
                quality_summary = {
                    "quality_score": float(quality_score),
                    "parse_success_ratio": quality_result["parse_success_ratio"],
                    "completeness_ratio": quality_result["completeness_ratio"],
                    "pattern_consistency_ratio": pattern_consistency_ratio,
                    "row_count": quality_result["row_count"],
                    "total_parse_error_cells": quality_result["total_parse_error_cells"],
                    "total_nullish_cells": quality_result["total_nullish_cells"],
                }
                normalized_rows = int(quality_result["row_count"])

                section_start = perf_counter()
                manifest = build_manifest_payload(
                    fingerprint=fingerprint,
                    source_checksums={"source_file": ingestion_result.file_checksum},
                    stage_metrics=stage_metrics,
                    quality_summary=quality_summary,
                    issue_summary=issue_summary,
                    normalized_checksum=normalized_checksum,
                    trace_checksum=trace_checksum,
                    effective_config=replay_config,
                    rules_version=effective.rules_version,
                    duckdb_version=duckdb_version,
                    normalized_path=normalized_path,
                    trace_path=trace_path,
                    manifest_path=manifest_path,
                )
                write_manifest(manifest_path, manifest)
                manifest_seconds = perf_counter() - section_start

                artifact_duration = perf_counter() - artifact_start
                stage_seconds["artifact_materialization"] = artifact_duration
                stage_metrics["artifact_materialization"] = {
                    "duration_seconds": artifact_duration,
                    "normalized_rows": normalized_rows,
                    "trace_rows": normalized_rows * len(data_columns),
                    "trace_mode": effective.trace_mode,
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

            elif run_mode == "APPLY":
                artifact_stage = ArtifactMaterializationStage()
                artifacts = artifact_stage.execute(
                    conn,
                    output_dir=output_root,
                    fingerprint=fingerprint,
                    trace_mode=effective.trace_mode,
                    source_checksums={"source_file": ingestion_result.file_checksum},
                    stage_metrics=stage_metrics,
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
                    rules_version=effective.rules_version,
                )
                stage_seconds["artifact_materialization"] = float(
                    artifact_stage.metrics.get("duration_seconds", 0.0)
                )
                stage_metrics["artifact_materialization"] = dict(artifact_stage.metrics)
        finally:
            if artifact_pool is not None:
                artifact_pool.shutdown(wait=True)

    return {
        "status": status.value,
        "quality_score": float(quality_score),
        "issues": [issue_to_dict(issue) for issue in issues],
        "fingerprint": fingerprint,
        "artifacts": artifacts if run_mode == "APPLY" else None,
        "stage_seconds": stage_seconds,
    }


def resolve_column_config_by_canonical(
    *,
    data_columns: list[str],
    column_config: dict[str, ColumnConfig] | Mapping[str, ColumnConfig],
) -> dict[str, ColumnConfig]:
    """Resolve position-keyed column config entries to canonical column names."""
    position_to_name = build_position_to_name(data_columns)
    resolved: dict[str, ColumnConfig] = {}
    for position_key, spec in column_config.items():
        canonical_name = position_to_name.get(position_key)
        if canonical_name is None:
            raise ValueError(
                "column_config position key "
                f"{position_key!r} is out of range for {len(data_columns)} columns"
            )
        resolved[canonical_name] = spec
    missing = sorted(column_name for column_name in data_columns if column_name not in resolved)
    if missing:
        raise ValueError(
            "column_config is missing declarations for columns: " f"{', '.join(missing)}"
        )
    return resolved
