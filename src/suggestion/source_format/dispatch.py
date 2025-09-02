"""Dispatch source format inference by declared format type."""

from __future__ import annotations

from pathlib import Path

from shared.models.operation import (
    CsvSourceFormat,
    ExcelSourceFormat,
    FileFormat,
    JsonSourceFormat,
)
from suggestion.constants import FILE_SAMPLE_BYTES
from suggestion.source_format.csv import infer_csv_source_format
from suggestion.source_format.excel import infer_excel_source_format
from suggestion.source_format.json import infer_json_source_format


def infer_source_format(
    source_file: Path,
    format_type: FileFormat,
) -> CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat:
    """
    Infer source format settings for the given file and declared format type.

    CSV inference reads FILE_SAMPLE_BYTES from disk; Excel probes the first
    sheet via openpyxl; JSON needs no inference.
    """
    if format_type == "csv":
        sample = source_file.read_bytes()[:FILE_SAMPLE_BYTES]
        return infer_csv_source_format(sample)
    if format_type == "excel":
        return infer_excel_source_format(source_file)
    return infer_json_source_format()
