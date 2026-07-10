"""JSON file-type inference for the AI strategy.

JSON is self-describing: no delimiter, no header, no encoding to guess. The
model receives raw JSON records and only types each field. Columns are matched
back to the parsed keys by name (JSON keys are named, unlike positional CSV).
"""

from __future__ import annotations

import json
from typing import cast

from shared.db.column_index import build_position_to_name
from shared.ingestion import resolve_ingestion_setup
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionConfidence
from shared.settings import get_settings
from shared.storage.probe import read_source_probe

from suggestion.ai.formats.base import (
    AiColumnInference,
    AiInferenceResult,
    FormatInference,
    ReconciledInference,
    make_core_output_model,
)
from suggestion.constants import FILE_SAMPLE_BYTES, JSON_FIRST_OBJECT_MAX_BYTES
from suggestion.source import SourceReading
from suggestion.source.json import (
    ensure_json_first_object_within_limit,
    infer_json_source_format,
    read_json_column_names_and_inference_rows,
    read_json_sample_objects,
    read_json_sample_rows,
)

_PROMPT = """\
You are given the first records of a JSON array of objects.

For each field (object key), report: its name (exactly as it appears), a
normalized type config, and your confidence (0.0-1.0) in that typing.

JSON sample:
{sample}
"""


class JsonAiInferenceResult(AiInferenceResult):
    """Model output for a JSON source (columns only)."""

    columns: list[AiColumnInference]


class JsonFormatInference(FormatInference):
    """JSON prompt, sampling, and reconciliation."""

    output_model = JsonAiInferenceResult
    core_output_model = make_core_output_model("CoreJsonAiInferenceResult", JsonAiInferenceResult)

    def sample(self, source: SourceRef) -> str:
        sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
        objects = read_json_sample_objects(sample_bytes, get_settings().ai_sample_row_count)
        return json.dumps(objects, ensure_ascii=False, indent=2)

    def build_prompt(self, sample: str) -> str:
        return _PROMPT.format(sample=sample)

    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        self.validate_result_type(result)
        result = cast(JsonAiInferenceResult, result)
        sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
        ensure_json_first_object_within_limit(sample_bytes[:JSON_FIRST_OBJECT_MAX_BYTES])
        column_names, inference_rows = read_json_column_names_and_inference_rows(sample_bytes)

        source_format = infer_json_source_format()
        setup = resolve_ingestion_setup(source, source_format)
        reading = SourceReading(
            source_format=source_format,
            sample_rows=read_json_sample_rows(sample_bytes),
            column_names=column_names,
            inference_rows=inference_rows,
            ingestion_source_url=setup.url,
            ingestion_source_type=setup.source_type,
            cleanup_path=setup.cleanup_path,
        )

        by_name = {col.name: col for col in result.columns}
        missing = [name for name in column_names if name not in by_name]
        if missing:
            raise ValueError(f"Model did not return configs for JSON fields: {missing}.")

        position_to_name = build_position_to_name(column_names)
        return ReconciledInference(
            reading=reading,
            column_config={pos: by_name[name].config for pos, name in position_to_name.items()},
            confidence=SuggestionConfidence(
                delimiter=None,
                header=None,
                column_config={
                    pos: by_name[name].confidence for pos, name in position_to_name.items()
                },
            ),
        )
