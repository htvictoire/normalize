"""
AI suggestion pipeline — infers provisional settings via an LLM.

Unlike the rule-based path (which resolves source_format heuristically up front
and can scan stats in parallel with column inference), the AI path resolves
source_format *from the model*, so the full-source stats scan can only run after
the model answers. Flow: decode text -> model call -> reconcile -> scan -> assemble.

Provider (which LLM) and format (which prompt/output schema) are orthogonal:
this module composes them and is blind to both.
"""

from __future__ import annotations

from shared.db.column_index import build_position_to_name
from shared.errors import SourceError
from shared.models.suggestion import SuggestionInput, SuggestionOutput

from suggestion.ai.formats import FORMATS
from suggestion.ai.providers import FileInferenceProvider, get_inference_provider
from suggestion.assembly import build_suggestion_output
from suggestion.display import read_sample_values
from suggestion.null_tokens import infer_null_tokens
from suggestion.stats import compute_source_stats


def run_suggestion(
    request: SuggestionInput,
    provider: FileInferenceProvider | None = None,
) -> SuggestionOutput:
    """Run the AI suggestion pipeline for one source file.

    ``provider`` is injectable for tests; production reads it from settings.
    """
    fmt = FORMATS[request.source_file_format]
    provider = provider or get_inference_provider()

    sample = fmt.sample(request)
    if not sample.strip():
        raise SourceError(f"Source file is empty: {request.source_file_name!r}")
    output_model = fmt.output_model_for_options(request.extended_type_detection)
    result = provider.infer_schema(fmt.build_prompt(sample), output_model)
    reconciled = fmt.reconcile(result, request)
    reading = reconciled.reading

    try:
        null_tokens = infer_null_tokens(reading.inference_rows, reading.column_names)
        position_to_name = build_position_to_name(reading.column_names)
        stats = compute_source_stats(reading, null_tokens, position_to_name)
        sample_values_by_position = read_sample_values(reading.inference_rows, position_to_name)
    finally:
        if reading.cleanup_path is not None:
            reading.cleanup_path.unlink(missing_ok=True)

    return build_suggestion_output(
        source_format=reading.source_format,
        column_config=reconciled.column_config,
        null_tokens=null_tokens,
        confidence=reconciled.confidence,
        stats=stats,
        sample_values_by_position=sample_values_by_position,
        sample_rows=reading.sample_rows,
        position_to_name=position_to_name,
    )
