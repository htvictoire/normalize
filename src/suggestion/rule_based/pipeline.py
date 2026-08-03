"""
Rule-based suggestion pipeline — infers provisional settings for one source file.

Phase 1  Read source: heuristically infer format settings, collect raw sample
         rows, and parse inference rows in one pass.

Phase 2  Derive null tokens and column position map from the inference rows.
         Both are pure-Python operations over in-memory data.

Phase 3  Run two tracks in parallel:
         Track A — one full-source scan returning exact row count and null counts
                   per column (no table materialization).
         Track B — infer a column config per column from the inference rows.

Phase 4  Assemble and return both phase outputs via the shared assembler.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from shared.db.column_index import build_position_to_name
from shared.models.column import ColumnConfig
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, SourceFormat
from shared.models.suggestion import (
    LayoutConfidence,
    LayoutOutput,
    SuggestionInput,
    TypingOutput,
)

from suggestion.assembly import build_layout_output, build_typing_output
from suggestion.null_tokens import infer_null_tokens
from suggestion.rule_based import infer_column_type, sample_column_values
from suggestion.rule_based.constants import RULE_BASED_CONFIDENCE
from suggestion.rule_based.source import read_source
from suggestion.source import SourceReading, read_under_format
from suggestion.stats import compute_source_stats


def _rule_based_layout_confidence(source_format: SourceFormat) -> LayoutConfidence:
    """Return the fixed confidence reported for every rule-based inference.

    Known limitation: this strategy does not estimate confidence. Detectors commit to
    the first type clearing a match threshold and discard the alternatives, so a column
    typed `string` for want of a match is indistinguishable from one typed `string` on
    evidence. A uniform value marks every inference as unscored. Confidence estimation
    belongs to the AI strategy; this path is for consumers that confirm before converting.
    """
    is_csv = isinstance(source_format, CsvSourceFormat)
    is_excel = isinstance(source_format, ExcelSourceFormat)
    return LayoutConfidence(
        delimiter=RULE_BASED_CONFIDENCE if is_csv else None,
        header=RULE_BASED_CONFIDENCE if (is_csv or is_excel) else None,
    )


def _infer_column_configs(
    reading: SourceReading,
    position_to_name: dict[str, str],
    extended_type_detection: bool,
) -> dict[str, ColumnConfig]:
    sampled = sample_column_values(reading.inference_rows, position_to_name)
    return {
        pos: infer_column_type(
            sampled[pos],
            extended_type_detection=extended_type_detection,
            column_name=name,
        )
        for pos, name in position_to_name.items()
    }


def run_layout(request: SuggestionInput) -> LayoutOutput:
    """Resolve one source's layout using rule-based heuristics, typing nothing."""
    with read_source(request) as reading:
        null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
        position_to_name = build_position_to_name(reading.column_names)
        stats = compute_source_stats(reading, null_tokens, position_to_name)
        return build_layout_output(
            reading,
            _rule_based_layout_confidence(reading.source_format),
            stats,
            null_tokens,
        )


def run_typing(request: SuggestionInput, layout: LayoutOutput) -> TypingOutput:
    """Type the columns of an already-resolved layout using rule-based heuristics."""
    with read_under_format(request, layout.source_format) as reading:
        position_to_name = build_position_to_name(reading.column_names)
        column_configs = _infer_column_configs(
            reading, position_to_name, request.extended_type_detection
        )
    return build_typing_output(
        layout, column_configs, dict.fromkeys(position_to_name, RULE_BASED_CONFIDENCE)
    )


def run_suggestion(
    request: SuggestionInput,
) -> tuple[LayoutOutput, TypingOutput]:
    """Run the rule-based suggestion pipeline for one source file in a single read.

    Prefer this over composing ``run_layout`` + ``run_typing`` when both phases use
    the rule-based strategy: it reads the source once and infers stats and column
    types in parallel, instead of reading twice.
    """
    with read_source(request) as reading:
        null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
        position_to_name = build_position_to_name(reading.column_names)
        with ThreadPoolExecutor(max_workers=2) as executor:
            stats_future = executor.submit(
                compute_source_stats, reading, null_tokens, position_to_name
            )
            configs_future = executor.submit(
                _infer_column_configs,
                reading,
                position_to_name,
                request.extended_type_detection,
            )
            stats = stats_future.result()
            column_configs = configs_future.result()
        layout = build_layout_output(
            reading,
            _rule_based_layout_confidence(reading.source_format),
            stats,
            null_tokens,
        )

    typing = build_typing_output(
        layout,
        column_configs,
        dict.fromkeys(position_to_name, RULE_BASED_CONFIDENCE),
    )
    return layout, typing
