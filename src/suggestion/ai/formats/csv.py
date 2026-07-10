"""CSV file-type inference for the AI strategy.

The model receives raw decoded CSV text (no delimiter or header pre-applied)
and returns the delimiter, header location, and per-column configs. Encoding is
resolved mechanically on our side (needed to decode bytes before the model can
read them); everything structural is the model's call.
"""

from __future__ import annotations

from typing import Literal, cast

from shared.ingestion import resolve_ingestion_setup
from shared.models.operation import CsvSourceFormat, HeaderMode
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
    pair_columns_by_position,
)
from suggestion.constants import FILE_SAMPLE_BYTES
from suggestion.source import SourceReading
from suggestion.source.csv import (
    infer_csv_encoding,
    read_csv_column_names_and_inference_rows,
    read_csv_sample_rows,
)

# The model names the delimiter (unambiguous, avoids escaping tab/newline in JSON);
# we map the name to the actual character for parsing.
DelimiterName = Literal["comma", "semicolon", "tab", "pipe"]
_DELIMITER_CHARS: dict[DelimiterName, str] = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}

_PROMPT = """\
You are given the first lines of a CSV file, exactly as stored (no parsing applied).

Determine:
1. The field delimiter (one of: comma, semicolon, tab, pipe).
2. Whether the file has a header row, and if so its 1-based row index; otherwise
   report the header as absent.
3. For each column, in left-to-right order: a name, its normalized type config,
   and your confidence (0.0-1.0) in that column's typing.

Also report your confidence (0.0-1.0) in the delimiter and header decisions.

CSV sample:
{sample}
"""


class CsvAiInferenceResult(AiInferenceResult):
    """Model output for a CSV source."""

    delimiter: DelimiterName
    delimiter_confidence: float
    header_mode: HeaderMode
    header_row_index: int | None
    header_confidence: float
    columns: list[AiColumnInference]


class CsvFormatInference(FormatInference):
    """CSV prompt, sampling, and reconciliation."""

    output_model = CsvAiInferenceResult
    core_output_model = make_core_output_model("CoreCsvAiInferenceResult", CsvAiInferenceResult)

    def sample(self, source: SourceRef) -> str:
        _, text = _read_decoded(source)
        row_count = get_settings().ai_sample_row_count
        return "\n".join(text.splitlines()[:row_count])

    def build_prompt(self, sample: str) -> str:
        return _PROMPT.format(sample=sample)

    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        self.validate_result_type(result)
        result = cast(CsvAiInferenceResult, result)
        encoding, text = _read_decoded(source)
        delimiter = _DELIMITER_CHARS[result.delimiter]

        source_format = CsvSourceFormat(
            encoding=encoding,
            delimiter=delimiter,
            header_mode=result.header_mode,
            header_row_index=result.header_row_index,
        )
        column_names, inference_rows = read_csv_column_names_and_inference_rows(
            text,
            delimiter=delimiter,
            header_mode=result.header_mode,
            header_row_index=result.header_row_index,
        )
        setup = resolve_ingestion_setup(source, source_format)
        reading = SourceReading(
            source_format=source_format,
            sample_rows=read_csv_sample_rows(text, delimiter),
            column_names=column_names,
            inference_rows=inference_rows,
            ingestion_source_url=setup.url,
            ingestion_source_type=setup.source_type,
            cleanup_path=setup.cleanup_path,
        )

        column_config, confidences = pair_columns_by_position(column_names, result.columns)
        return ReconciledInference(
            reading=reading,
            column_config=column_config,
            confidence=SuggestionConfidence(
                delimiter=result.delimiter_confidence,
                header=result.header_confidence,
                column_config=confidences,
            ),
        )


def _read_decoded(source: SourceRef) -> tuple[str, str]:
    """Read the probe bytes once and return (encoding, decoded_text)."""
    sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
    encoding = infer_csv_encoding(sample_bytes)
    return encoding, sample_bytes.decode(encoding, errors="ignore")
