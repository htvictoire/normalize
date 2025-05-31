"""Engine runtime configuration contract."""

from __future__ import annotations

from dataclasses import dataclass

from normalize.stages.ingestion.contracts import HeaderMode


@dataclass(frozen=True)
class EngineConfig:
    """Runtime config for Phase 1 engine orchestration."""

    rules_version: str
    duckdb_path: str
    header_mode: HeaderMode
    header_row_index: int | None
    encoding: str
    delimiter: str
    null_tokens: tuple[str, ...]
    boolean_true_tokens: tuple[str, ...]
    boolean_false_tokens: tuple[str, ...]
    type_inference_numeric_threshold: float
    type_inference_boolean_threshold: float
    assign_indices: bool
    drop_empty_rows: bool
    full_raw_row: bool
    emit_raw_row: bool
    emit_parse_issues: bool
    include_unique_ratio: bool
    include_per_column_parse_error_counts: bool
    approximate_unique: bool
    decision_ready_threshold: float
    decision_warning_threshold: float
    trace_mode: str  # "full" or "sparse"
    threads: int
