"""Shared assembly of phase outputs, strategy-independent.

Both strategies reach the same two milestones: a source parsed under a resolved
layout, then a config for each of its columns. The operation defaults, display,
and duration estimate are identical however the layout was resolved and however
the columns were typed, so they are built here once.
"""

from __future__ import annotations

from shared.db.column_index import build_position_to_name
from shared.models.column import ColumnConfig
from shared.models.instance_config import InstanceConfig
from shared.models.operation import DecisionThresholds, OperationConfig
from shared.models.profiling import ColumnCountResult
from shared.models.suggestion import (
    LayoutConfidence,
    LayoutOutput,
    SuggestedColumnDisplay,
    SuggestionDisplay,
    TypingOutput,
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
    LOW_CONFIDENCE_THRESHOLD,
)
from suggestion.display import read_sample_values
from suggestion.duration import estimate_pipeline_seconds
from suggestion.issues import build_low_confidence_issue
from suggestion.source import SourceReading


def build_layout_output(
    reading: SourceReading,
    confidence: LayoutConfidence,
    stats: ColumnCountResult,
    null_tokens: tuple[str, ...],
) -> LayoutOutput:
    """Assemble everything a parsed source yields before anything is typed.

    ``stats`` and ``null_tokens`` are passed in rather than computed here: the
    scan that produces them is the one step a strategy may want to overlap with
    its own work, so where it runs is the caller's decision.
    """
    position_to_name = build_position_to_name(reading.column_names)
    sample_values = read_sample_values(reading.inference_rows, position_to_name)
    return LayoutOutput(
        source_format=reading.source_format,
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
        display=SuggestionDisplay(
            row_count=stats.row_count,
            columns={
                pos: SuggestedColumnDisplay(
                    label=name,
                    counts=stats.column_counts[pos],
                    sample_values=sample_values[pos],
                )
                for pos, name in position_to_name.items()
            },
            sample_rows=reading.sample_rows,
        ),
        confidence=confidence,
        estimated_pipeline_seconds=estimate_pipeline_seconds(stats.row_count),
    )


def build_typing_output(
    layout: LayoutOutput,
    column_config: dict[str, ColumnConfig],
    column_confidence: dict[str, float],
) -> TypingOutput:
    """Assemble a typing answer, raising the issues its confidence warrants."""
    low_confidence = build_low_confidence_issue(
        layout.confidence,
        column_confidence,
        layout.display,
        LOW_CONFIDENCE_THRESHOLD,
    )
    return TypingOutput(
        column_config=column_config,
        confidence=column_confidence,
        issues=[low_confidence] if low_confidence is not None else [],
    )


def build_instance_config(layout: LayoutOutput, typing: TypingOutput) -> InstanceConfig:
    """Compose the config a consumer confirms from the two phases that decided it."""
    return InstanceConfig(
        source_format=layout.source_format,
        column_config=typing.column_config,
        operation_config=layout.operation_config,
    )
