"""
AI suggestion pipeline — composes the layout and typing phases.

Layout resolves the SourceFormat and parses the file under it; typing infers a
config per parsed column. Each phase is callable on its own, so a consumer can
present a source's columns as soon as the layout lands and wait for typing only
where a column type actually matters.

Provider (which LLM) and format (which prompt/output schema) are orthogonal:
this module composes them and is blind to both.
"""

from __future__ import annotations

from shared.db.column_index import build_position_to_name
from shared.models.suggestion import LayoutOutput, SuggestionInput, TypingOutput

from suggestion.ai.formats import FORMATS
from suggestion.ai.layout import resolve_layout
from suggestion.ai.providers import FileInferenceProvider
from suggestion.ai.typing_phase import type_columns
from suggestion.assembly import build_layout_output, build_typing_output
from suggestion.null_tokens import infer_null_tokens
from suggestion.source import effective_file_format
from suggestion.stats import compute_source_stats


def run_layout(
    request: SuggestionInput,
    provider: FileInferenceProvider | None = None,
) -> LayoutOutput:
    """Resolve and parse one source's layout, typing nothing.

    ``provider`` is injectable for tests; production reads it from settings.
    """
    fmt = FORMATS[effective_file_format(request)]
    reading, confidence = resolve_layout(fmt, request, provider)
    with reading:
        null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
        position_to_name = build_position_to_name(reading.column_names)
        stats = compute_source_stats(reading, null_tokens, position_to_name)
        return build_layout_output(reading, confidence, stats, null_tokens)


def run_typing(
    request: SuggestionInput,
    layout: LayoutOutput,
    provider: FileInferenceProvider | None = None,
) -> TypingOutput:
    """Type the columns of an already-resolved layout."""
    fmt = FORMATS[effective_file_format(request)]
    with fmt.read(request, layout.source_format) as reading:
        column_config, column_confidence = type_columns(
            reading, request.extended_type_detection, provider
        )
    return build_typing_output(layout, column_config, column_confidence)


def run_suggestion(
    request: SuggestionInput,
    provider: FileInferenceProvider | None = None,
) -> tuple[LayoutOutput, TypingOutput]:
    """Run both AI phases for one source file."""
    layout = run_layout(request, provider)
    return layout, run_typing(request, layout, provider)
