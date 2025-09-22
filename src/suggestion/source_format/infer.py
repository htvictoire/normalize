"""Dispatch source format inference by declared format type."""

from __future__ import annotations

from pathlib import Path

from shared.models.operation import CsvSourceFormat, FileFormat, SourceFormat
from suggestion.constants import FILE_SAMPLE_BYTES
from suggestion.source.csv import infer_csv_source_format
from suggestion.source.excel import read_excel_source
from suggestion.source.json import infer_json_source_format


def infer_source_format(
    source_file: Path,
    source_file_format: FileFormat,
) -> SourceFormat:
    """
    Infer source format settings for the given file and declared format type.

    CSV inference reads FILE_SAMPLE_BYTES from disk; Excel probes the first
    sheet via openpyxl; JSON needs no inference.
    """
    if source_file_format == "csv":
        sample = source_file.read_bytes()[:FILE_SAMPLE_BYTES]
        return infer_csv_source_format(sample)
    if source_file_format == "excel":
        return read_excel_source(source_file)[0]
    return infer_json_source_format()


def infer_source_format_from_bytes(sample: bytes) -> CsvSourceFormat:
    """Infer CSV source format from an already-read sample."""
    return infer_csv_source_format(sample)
