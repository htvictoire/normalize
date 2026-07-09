"""
Rule-based suggestion pipeline — infers provisional settings for one source file.

Phase 1  Read source: heuristically infer format settings, collect raw sample
         rows, and parse inference rows in one pass.

Phase 2  Derive null tokens and column position map from the inference rows.
         Both are pure-Python operations over in-memory data.

Phase 3  Run two tracks in parallel:
         Track A — one full-source scan returning exact row count and null counts
                   per column (no table materialization).
         Track B — infer column configs and collect display values from the
                   inference rows.

Phase 4  Assemble and return a SuggestionResult containing the suggested
         InstanceConfig and the display-only SuggestionDisplay.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from shared.db.column_index import build_position_to_name
from shared.models.column import ColumnConfig
from shared.models.instance_config import InstanceConfig
from shared.models.operation import (
    CsvSourceFormat,
    DecisionThresholds,
    ExcelSourceFormat,
    OperationConfig,
    SourceFormat,
)
from shared.models.source import SourceRef
from shared.models.suggestion import (
    SuggestedColumnDisplay,
    SuggestionConfidence,
    SuggestionDisplay,
    SuggestionOutput,
)

from suggestion.constants import (
    DEFAULT_APPROXIMATE_UNIQUE,
    DEFAULT_ASSIGN_INDICES,
    DEFAULT_DECISION_READY,
    DEFAULT_DECISION_WARNING,
    DEFAULT_DROP_EMPTY_ROWS,
    DEFAULT_EMIT_PARSE_ISSUES,
    DEFAULT_EMIT_RAW_ROW,
    DEFAULT_FULL_RAW_ROW,
    DEFAULT_INCLUDE_PER_COLUMN_PARSE_ERROR_COUNTS,
    DEFAULT_INCLUDE_UNIQUE_RATIO,
    DEFAULT_TRACE_MODE,
)
from suggestion.display import read_sample_values
from suggestion.duration import estimate_pipeline_seconds
from suggestion.rule_based import infer_column_type, sample_column_values
from suggestion.rule_based.null_tokens import infer_null_tokens
from suggestion.rule_based.source import read_source
from suggestion.source import SourceReading
from suggestion.stats import compute_source_stats


@dataclass(frozen=True)
class _CoreSuggestion:
    column_configs: dict[str, ColumnConfig]
    sample_values_by_position: dict[str, list[str]]


def _rule_based_confidence(
    source_format: SourceFormat,
    position_to_name: dict[str, str],
) -> SuggestionConfidence:
    """Deterministic rule-based inference reports full confidence for everything it guesses.

    delimiter/header are None for formats that do not have them (Excel has no
    delimiter; JSON has neither).
    """
    is_csv = isinstance(source_format, CsvSourceFormat)
    is_excel = isinstance(source_format, ExcelSourceFormat)
    return SuggestionConfidence(
        delimiter=1.0 if is_csv else None,
        header=1.0 if (is_csv or is_excel) else None,
        column_config=dict.fromkeys(position_to_name, 1.0),
    )


def _run_core(reading: SourceReading, position_to_name: dict[str, str]) -> _CoreSuggestion:
    sampled_values_by_position = sample_column_values(reading.inference_rows, position_to_name)
    column_configs = {
        pos: infer_column_type(sampled_values_by_position[pos])
        for pos in position_to_name
    }
    sample_values_by_position = read_sample_values(reading.inference_rows, position_to_name)
    return _CoreSuggestion(
        column_configs=column_configs,
        sample_values_by_position=sample_values_by_position,
    )


def run_suggestion(source: SourceRef) -> SuggestionOutput:
    """Run the rule-based suggestion pipeline for one source file."""
    reading = read_source(source)

    null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
    position_to_name = build_position_to_name(reading.column_names)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            stats_future = executor.submit(
                compute_source_stats, reading, null_tokens, position_to_name
            )
            core_future = executor.submit(_run_core, reading, position_to_name)
            stats = stats_future.result()
            core = core_future.result()
    finally:
        if reading.cleanup_path is not None:
            reading.cleanup_path.unlink(missing_ok=True)

    suggested_config = InstanceConfig(
        source_format=reading.source_format,
        column_config=core.column_configs,
        operation_config=OperationConfig(
            null_tokens=null_tokens,
            assign_indices=DEFAULT_ASSIGN_INDICES,
            drop_empty_rows=DEFAULT_DROP_EMPTY_ROWS,
            emit_raw_row=DEFAULT_EMIT_RAW_ROW,
            full_raw_row=DEFAULT_FULL_RAW_ROW,
            emit_parse_issues=DEFAULT_EMIT_PARSE_ISSUES,
            include_unique_ratio=DEFAULT_INCLUDE_UNIQUE_RATIO,
            include_per_column_parse_error_counts=DEFAULT_INCLUDE_PER_COLUMN_PARSE_ERROR_COUNTS,
            approximate_unique=DEFAULT_APPROXIMATE_UNIQUE,
            trace_mode=DEFAULT_TRACE_MODE,
            decision_thresholds=DecisionThresholds(
                ready=DEFAULT_DECISION_READY,
                warning=DEFAULT_DECISION_WARNING,
            ),
        ),
    )
    display = SuggestionDisplay(
        row_count=stats.row_count,
        columns={
            pos: SuggestedColumnDisplay(
                label=position_to_name[pos],
                counts=stats.column_counts[pos],
                sample_values=core.sample_values_by_position[pos],
            )
            for pos in position_to_name
        },
        sample_rows=reading.sample_rows,
    )
    return SuggestionOutput(
        suggested_config=suggested_config,
        confidence=_rule_based_confidence(reading.source_format, position_to_name),
        display=display,
        estimated_pipeline_seconds=estimate_pipeline_seconds(stats.row_count),
    )
