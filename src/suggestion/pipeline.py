"""
Suggestion pipeline — infers provisional settings for one source file.

Phase 1  Read source: infer format settings, collect raw sample rows, and parse
         inference rows in one pass.

Phase 2  Derive null tokens and column position map from the inference rows.
         Both are pure-Python operations over in-memory data.

Phase 3  Run two tracks in parallel:
         Track A — one full-source scan returning exact row count and null counts
                   per column (no table materialization).
         Track B — infer column configs and collect display values from the
                   inference rows.

Phase 4  Assemble the final SuggestionOutput from both tracks.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from shared.models.column import ColumnConfig
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestedColumn, SuggestionOutput
from shared.utils.column import build_position_to_name
from suggestion.column_config.inference import infer_column_type
from suggestion.column_config.sampler import sample_column_values
from suggestion.column_display import read_sample_values
from suggestion.null_tokens import infer_null_tokens
from suggestion.source.read import SourceReading, read_source
from suggestion.source_stats import compute_source_stats


@dataclass(frozen=True)
class _CoreSuggestion:
    column_configs: dict[str, ColumnConfig]
    sample_values_by_position: dict[str, list[str]]


def _run_core(reading: SourceReading, position_to_name: dict[str, str]) -> _CoreSuggestion:
    sampled_values = sample_column_values(reading.inference_rows, reading.column_names)
    column_configs = {
        pos: infer_column_type(sampled_values[name])
        for pos, name in position_to_name.items()
    }
    sample_values_by_position = read_sample_values(reading.inference_rows, position_to_name)
    return _CoreSuggestion(
        column_configs=column_configs,
        sample_values_by_position=sample_values_by_position,
    )


def run_suggestion(source: SourceRef) -> SuggestionOutput:
    """Run the suggestion pipeline for one source file."""
    reading = read_source(source)

    null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
    position_to_name = build_position_to_name(reading.column_names)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            stats_future = executor.submit(
                compute_source_stats, reading, null_tokens, position_to_name
            )
            core_future = executor.submit(_run_core, reading, position_to_name)
            row_count, column_counts = stats_future.result()
            core = core_future.result()
    finally:
        if reading.cleanup_path is not None:
            reading.cleanup_path.unlink(missing_ok=True)

    return SuggestionOutput(
        source_format=reading.source_format,
        null_tokens=null_tokens,
        row_count=row_count,
        columns={
            pos: SuggestedColumn(
                label=position_to_name[pos],
                config=core.column_configs[pos],
                counts=column_counts[pos],
                sample_values=core.sample_values_by_position[pos],
            )
            for pos in position_to_name
        },
        sample_rows=reading.sample_rows,
    )
