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

Phase 4  Assemble and return the SuggestionOutput via the shared assembler.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from shared.db.column_index import build_position_to_name
from shared.models.column import ColumnConfig
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, SourceFormat
from shared.models.suggestion import SuggestionConfidence, SuggestionInput, SuggestionOutput

from suggestion.assembly import build_suggestion_output
from suggestion.display import read_sample_values
from suggestion.null_tokens import infer_null_tokens
from suggestion.rule_based import infer_column, sample_column_values
from suggestion.rule_based.source import read_source
from suggestion.source import SourceReading
from suggestion.stats import compute_source_stats


@dataclass(frozen=True)
class _CoreSuggestion:
    column_configs: dict[str, ColumnConfig]
    column_confidences: dict[str, float]
    sample_values_by_position: dict[str, list[str]]


def _rule_based_confidence(
    source_format: SourceFormat,
    position_to_name: dict[str, str],
    column_confidences: dict[str, float],
) -> SuggestionConfidence:
    """Return rule-based confidence values for format and column inferences."""
    is_csv = isinstance(source_format, CsvSourceFormat)
    is_excel = isinstance(source_format, ExcelSourceFormat)
    return SuggestionConfidence(
        delimiter=1.0 if is_csv else None,
        header=1.0 if (is_csv or is_excel) else None,
        column_config={pos: column_confidences[pos] for pos in position_to_name},
    )


def _run_core(
    reading: SourceReading,
    position_to_name: dict[str, str],
    extended_type_detection: bool,
) -> _CoreSuggestion:
    sampled_values_by_position = sample_column_values(reading.inference_rows, position_to_name)
    inferences = {
        pos: infer_column(
            sampled_values_by_position[pos],
            extended_type_detection=extended_type_detection,
            column_name=position_to_name[pos],
        )
        for pos in position_to_name
    }
    sample_values_by_position = read_sample_values(reading.inference_rows, position_to_name)
    return _CoreSuggestion(
        column_configs={pos: inference.config for pos, inference in inferences.items()},
        column_confidences={pos: inference.confidence for pos, inference in inferences.items()},
        sample_values_by_position=sample_values_by_position,
    )


def run_suggestion(
    request: SuggestionInput,
) -> SuggestionOutput:
    """Run the rule-based suggestion pipeline for one source file."""
    reading = read_source(request)

    null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
    position_to_name = build_position_to_name(reading.column_names)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            stats_future = executor.submit(
                compute_source_stats, reading, null_tokens, position_to_name
            )
            core_future = executor.submit(
                _run_core,
                reading,
                position_to_name,
                request.extended_type_detection,
            )
            stats = stats_future.result()
            core = core_future.result()
    finally:
        if reading.cleanup_path is not None:
            reading.cleanup_path.unlink(missing_ok=True)

    return build_suggestion_output(
        source_format=reading.source_format,
        column_config=core.column_configs,
        null_tokens=null_tokens,
        confidence=_rule_based_confidence(
            reading.source_format,
            position_to_name,
            core.column_confidences,
        ),
        stats=stats,
        sample_values_by_position=core.sample_values_by_position,
        sample_rows=reading.sample_rows,
        position_to_name=position_to_name,
    )
