"""Excel layout inference and reading for the AI strategy.

Sheet selection stays mechanical (first visible non-empty worksheet), leaving the
model one decision: where the header row is. Cells are not delimited text, so
there is no delimiter to name.

Excel stats are computed from the in-memory rows rather than a DuckDB scan, so
the worksheet is loaded locally and any S3 temp file cleaned up here.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from shared.models.operation import ExcelSourceFormat, HeaderMode, SourceFormat
from shared.models.source import SourceRef
from shared.models.suggestion import LayoutConfidence
from shared.storage.s3 import download_s3_temp, s3_ref

from suggestion.ai.formats.base import InferredLayout, LayoutAnswer
from suggestion.constants import LAYOUT_SAMPLE_ROWS
from suggestion.source import SourceReading, read_under_format
from suggestion.source.excel import assemble_excel_reading, read_excel_raw_rows, row_to_strings

_LAYOUT_PROMPT = """\
You are given the first rows of a spreadsheet as a JSON array of rows, in order
starting at row 1. Each row is an array of cell values (strings), left to right.

Determine whether there is a header row, and if so its 1-based row index
(matching the order given); otherwise report the header as absent.

Report your confidence (0.0-1.0) in that decision.

Spreadsheet rows:
{sample}
"""


class ExcelLayoutAnswer(LayoutAnswer):
    """The header row the model read off a spreadsheet grid."""

    header_mode: HeaderMode
    header_row_index: int | None
    header_confidence: float = Field(ge=0.0, le=1.0)


class ExcelFormatInference(InferredLayout[ExcelLayoutAnswer]):
    """Excel layout inference and reading."""

    @property
    def layout_answer(self) -> type[ExcelLayoutAnswer]:
        return ExcelLayoutAnswer

    def layout_sample(self, source: SourceRef) -> str:
        _, all_rows = _load_rows(source)
        grid = [row_to_strings(row) for row in all_rows[:LAYOUT_SAMPLE_ROWS]]
        return json.dumps(grid, ensure_ascii=False, indent=2)

    def build_layout_prompt(self, sample: str) -> str:
        return _LAYOUT_PROMPT.format(sample=sample)

    def to_source_format(self, answer: ExcelLayoutAnswer, source: SourceRef) -> SourceFormat:
        sheet_name, all_rows = _load_rows(source)
        source_format, _, _, _ = assemble_excel_reading(
            sheet_name,
            all_rows,
            answer.header_mode,
            answer.header_row_index,
        )
        return source_format

    def layout_confidence(self, answer: ExcelLayoutAnswer) -> LayoutConfidence:
        return LayoutConfidence(header=answer.header_confidence)

    def read(self, source: SourceRef, source_format: SourceFormat) -> SourceReading:
        if not isinstance(source_format, ExcelSourceFormat):
            raise TypeError(f"Expected an Excel layout, got {type(source_format).__name__}.")
        return read_under_format(source, source_format)


def _load_rows(source: SourceRef) -> tuple[str, list[tuple[object, ...]]]:
    """Load the selected worksheet's (sheet_name, all_rows), cleaning up any S3 temp file."""
    if source.source_file is None:
        raise ValueError("Excel source has no source_file; it cannot be read from a sample.")
    if source.source_type == "s3":
        temp_path = download_s3_temp(s3_ref(source.source_file))
        try:
            return read_excel_raw_rows(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
    return read_excel_raw_rows(Path(source.source_file))
