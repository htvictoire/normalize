"""Shared final assembly of a SuggestionOutput, strategy-independent.

Both the rule-based and AI strategies produce the same raw ingredients
(a resolved source_format, a per-position column_config, null tokens, a
confidence, full-source stats, and display samples). This module turns those
into the SuggestionOutput — the operation_config defaults, display, and
duration estimate are identical regardless of how the config was inferred.
"""

from __future__ import annotations

from shared.models.column import ColumnConfig
from shared.models.instance_config import InstanceConfig
from shared.models.operation import DecisionThresholds, OperationConfig, SourceFormat
from shared.models.profiling import ColumnCountResult
from shared.models.suggestion import (
    SuggestedColumnDisplay,
    SuggestionConfidence,
    SuggestionDisplay,
    SuggestionOutput,
)

from suggestion.constants import (
    DEFAULT_APPROXIMATE_UNIQUE,
    DEFAULT_DECISION_READY,
    DEFAULT_DECISION_WARNING,
    DEFAULT_DROP_EMPTY_ROWS,
    DEFAULT_FULL_RAW_ROW,
    DEFAULT_INCLUDE_PER_COLUMN_PARSE_ERROR_COUNTS,
    DEFAULT_INCLUDE_UNIQUE_RATIO,
    DEFAULT_TRACE_MODE,
)
from suggestion.duration import estimate_pipeline_seconds


def build_suggestion_output(
    source_format: SourceFormat,
    column_config: dict[str, ColumnConfig],
    null_tokens: tuple[str, ...],
    confidence: SuggestionConfidence,
    stats: ColumnCountResult,
    sample_values_by_position: dict[str, list[str]],
    sample_rows: list[list[str]],
    position_to_name: dict[str, str],
) -> SuggestionOutput:
    """Assemble the final SuggestionOutput from strategy-produced ingredients."""
    suggested_config = InstanceConfig(
        source_format=source_format,
        column_config=column_config,
        operation_config=OperationConfig(
            null_tokens=null_tokens,
            drop_empty_rows=DEFAULT_DROP_EMPTY_ROWS,
            full_raw_row=DEFAULT_FULL_RAW_ROW,
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
                sample_values=sample_values_by_position[pos],
            )
            for pos in position_to_name
        },
        sample_rows=sample_rows,
    )
    return SuggestionOutput(
        suggested_config=suggested_config,
        confidence=confidence,
        display=display,
        estimated_pipeline_seconds=estimate_pipeline_seconds(stats.row_count),
    )
