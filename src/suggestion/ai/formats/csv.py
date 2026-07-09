"""CSV file-type inference for the AI strategy.

The model receives raw decoded CSV text (no delimiter or header pre-applied)
and returns the delimiter, header location, and per-column configs. Encoding is
resolved mechanically on our side (needed to decode bytes before the model can
read them); everything structural is the model's call.
"""

from __future__ import annotations

from shared.db.column_index import build_position_to_name
from shared.models.operation import CsvSourceFormat, HeaderMode
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionConfidence
from shared.settings import get_settings
from shared.storage.probe import read_source_probe
from shared.storage.s3 import build_duckdb_s3_url, s3_ref

from suggestion.ai.formats.base import (
    AiColumnInference,
    AiInferenceResult,
    FormatInference,
    ReconciledInference,
)
from suggestion.constants import FILE_SAMPLE_BYTES
from suggestion.source import SourceReading
from suggestion.source.csv import (
    infer_csv_encoding,
    read_csv_column_names_and_inference_rows,
    read_csv_sample_rows,
)

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

    delimiter: str
    delimiter_confidence: float
    header_mode: HeaderMode
    header_row_index: int | None
    header_confidence: float
    columns: list[AiColumnInference]


class CsvFormatInference(FormatInference):
    """CSV prompt, sampling, and reconciliation."""

    output_model = CsvAiInferenceResult

    def sample(self, source: SourceRef) -> str:
        _, text = _read_decoded(source)
        row_count = get_settings().ai_sample_row_count
        return "\n".join(text.splitlines()[:row_count])

    def build_prompt(self, sample: str) -> str:
        return _PROMPT.format(sample=sample)

    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        if not isinstance(result, CsvAiInferenceResult):
            raise TypeError(
                f"CSV reconcile expected CsvAiInferenceResult, got {type(result).__name__}."
            )
        encoding, text = _read_decoded(source)

        source_format = CsvSourceFormat(
            encoding=encoding,
            delimiter=result.delimiter,
            header_mode=result.header_mode,
            header_row_index=result.header_row_index,
        )
        column_names, inference_rows = read_csv_column_names_and_inference_rows(
            text,
            delimiter=result.delimiter,
            header_mode=result.header_mode,
            header_row_index=result.header_row_index,
        )
        reading = SourceReading(
            source_format=source_format,
            sample_rows=read_csv_sample_rows(text, result.delimiter),
            column_names=column_names,
            inference_rows=inference_rows,
            ingestion_source_url=_ingestion_url(source),
            ingestion_source_type=source.source_type,
            cleanup_path=None,
        )

        positions = list(build_position_to_name(column_names).keys())
        if len(result.columns) != len(positions):
            raise ValueError(
                f"Model returned {len(result.columns)} columns but the CSV parsed into "
                f"{len(positions)} under delimiter {result.delimiter!r}."
            )
        paired = list(zip(positions, result.columns, strict=True))
        return ReconciledInference(
            reading=reading,
            column_config={pos: col.config for pos, col in paired},
            confidence=SuggestionConfidence(
                delimiter=result.delimiter_confidence,
                header=result.header_confidence,
                column_config={pos: col.confidence for pos, col in paired},
            ),
        )


def _read_decoded(source: SourceRef) -> tuple[str, str]:
    """Read the probe bytes once and return (encoding, decoded_text)."""
    sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
    encoding = infer_csv_encoding(sample_bytes)
    return encoding, sample_bytes.decode(encoding, errors="ignore")


def _ingestion_url(source: SourceRef) -> str:
    if source.source_type == "s3":
        return build_duckdb_s3_url(s3_ref(source.source_file))
    return source.source_file
