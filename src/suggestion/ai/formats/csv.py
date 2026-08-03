"""CSV layout inference and reading for the AI strategy.

The model sees raw decoded text with nothing pre-applied and names the delimiter
and header row. Encoding is resolved mechanically, since bytes must be decoded
before there is any text for the model to read.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from shared.models.operation import CsvSourceFormat, HeaderMode, SourceFormat
from shared.models.source import SourceRef
from shared.models.suggestion import LayoutConfidence
from shared.storage.probe import read_source_probe

from suggestion.ai.formats.base import InferredLayout, LayoutAnswer
from suggestion.constants import FILE_SAMPLE_BYTES, LAYOUT_SAMPLE_ROWS
from suggestion.source import SourceReading, read_under_format
from suggestion.source.csv import infer_csv_encoding

# The model names the delimiter rather than emitting it, which keeps tab and
# newline out of the JSON it has to escape.
DelimiterName = Literal["comma", "semicolon", "tab", "pipe"]
_DELIMITER_CHARS: dict[DelimiterName, str] = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}

_LAYOUT_PROMPT = """\
You are given the first lines of a CSV file, exactly as stored (no parsing applied).

Determine:
1. The field delimiter (one of: comma, semicolon, tab, pipe).
2. Whether the file has a header row, and if so its 1-based row index; otherwise
   report the header as absent.

Report your confidence (0.0-1.0) in each decision separately.

CSV sample:
{sample}
"""


class CsvLayoutAnswer(LayoutAnswer):
    """The delimiter and header row the model read off a CSV sample."""

    delimiter: DelimiterName
    delimiter_confidence: float = Field(ge=0.0, le=1.0)
    header_mode: HeaderMode
    header_row_index: int | None
    header_confidence: float = Field(ge=0.0, le=1.0)


class CsvFormatInference(InferredLayout[CsvLayoutAnswer]):
    """CSV layout inference and reading."""

    @property
    def layout_answer(self) -> type[CsvLayoutAnswer]:
        return CsvLayoutAnswer

    def layout_sample(self, source: SourceRef) -> str:
        _, text = _decode(source)
        return "\n".join(text.splitlines()[:LAYOUT_SAMPLE_ROWS])

    def build_layout_prompt(self, sample: str) -> str:
        return _LAYOUT_PROMPT.format(sample=sample)

    def to_source_format(self, answer: CsvLayoutAnswer, source: SourceRef) -> SourceFormat:
        encoding, _ = _decode(source)
        return CsvSourceFormat(
            encoding=encoding,
            delimiter=_DELIMITER_CHARS[answer.delimiter],
            header_mode=answer.header_mode,
            header_row_index=answer.header_row_index,
        )

    def layout_confidence(self, answer: CsvLayoutAnswer) -> LayoutConfidence:
        return LayoutConfidence(
            delimiter=answer.delimiter_confidence,
            header=answer.header_confidence,
        )

    def read(self, source: SourceRef, source_format: SourceFormat) -> SourceReading:
        if not isinstance(source_format, CsvSourceFormat):
            raise TypeError(f"Expected a CSV layout, got {type(source_format).__name__}.")
        return read_under_format(source, source_format)


def _decode(source: SourceRef, encoding: str | None = None) -> tuple[str, str]:
    """Read the probe bytes once and return (encoding, decoded_text)."""
    sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
    resolved = encoding or infer_csv_encoding(sample_bytes)
    return resolved, sample_bytes.decode(resolved, errors="ignore")
