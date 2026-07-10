"""Excel file-type inference for the AI strategy.

Sheet selection stays mechanical (first visible non-empty worksheet). The model
receives the sheet's first rows rendered as a text grid and decides the header
location and per-column types — no delimiter (cells, not delimited text).

Excel stats are computed from the in-memory rows (not a DuckDB scan), so the
worksheet is loaded locally, sliced, and any S3 temp file cleaned up here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from shared.models.operation import HeaderMode
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionConfidence
from shared.settings import get_settings
from shared.storage.s3 import download_s3_temp, s3_ref

from suggestion.ai.formats.base import (
    AiColumnInference,
    AiInferenceResult,
    FormatInference,
    ReconciledInference,
    make_core_output_model,
    pair_columns_by_position,
)
from suggestion.source import SourceReading
from suggestion.source.excel import assemble_excel_reading, read_excel_raw_rows, row_to_strings

_PROMPT = """\
You are given the first rows of a spreadsheet as a JSON array of rows, in order
starting at row 1. Each row is an array of cell values (strings), left to right.

Determine:
1. Whether there is a header row, and if so its 1-based row index (matching the
   order given); otherwise report the header as absent.
2. For each column, left-to-right: a name, its normalized type config, and your
   confidence (0.0-1.0) in that column's typing.

Also report your confidence (0.0-1.0) in the header decision.

Spreadsheet rows:
{sample}
"""


class ExcelAiInferenceResult(AiInferenceResult):
    """Model output for an Excel source (no delimiter)."""

    header_mode: HeaderMode
    header_row_index: int | None
    header_confidence: float
    columns: list[AiColumnInference]


class ExcelFormatInference(FormatInference):
    """Excel prompt, sampling, and reconciliation."""

    output_model = ExcelAiInferenceResult
    core_output_model = make_core_output_model(
        "CoreExcelAiInferenceResult",
        ExcelAiInferenceResult,
    )

    def sample(self, source: SourceRef) -> str:
        _, all_rows = _load_rows(source)
        row_count = get_settings().ai_sample_row_count
        grid = [row_to_strings(row) for row in all_rows[:row_count]]
        return json.dumps(grid, ensure_ascii=False, indent=2)

    def build_prompt(self, sample: str) -> str:
        return _PROMPT.format(sample=sample)

    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        self.validate_result_type(result)
        result = cast(ExcelAiInferenceResult, result)
        sheet_name, all_rows = _load_rows(source)
        source_format, sample_rows, column_names, inference_rows = assemble_excel_reading(
            sheet_name,
            all_rows,
            result.header_mode,
            result.header_row_index,
        )
        # Excel stats read the in-memory rows, so the ingestion URL is unused here.
        reading = SourceReading(
            source_format=source_format,
            sample_rows=sample_rows,
            column_names=column_names,
            inference_rows=inference_rows,
            ingestion_source_url=source.source_file,
            ingestion_source_type="local",
            cleanup_path=None,
        )

        column_config, confidences = pair_columns_by_position(column_names, result.columns)
        return ReconciledInference(
            reading=reading,
            column_config=column_config,
            confidence=SuggestionConfidence(
                delimiter=None,
                header=result.header_confidence,
                column_config=confidences,
            ),
        )


def _load_rows(source: SourceRef) -> tuple[str, list[tuple[object, ...]]]:
    """Load the selected worksheet's (sheet_name, all_rows), cleaning up any S3 temp file."""
    if source.source_type == "s3":
        temp_path = download_s3_temp(s3_ref(source.source_file))
        try:
            return read_excel_raw_rows(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
    return read_excel_raw_rows(Path(source.source_file))
