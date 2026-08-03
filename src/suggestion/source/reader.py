"""Read one source under an already-resolved format.

Format-agnostic to strategy: layout may have been resolved by either the AI or
the rule-based strategy, so this only depends on the SourceFormat itself, not
on how it was chosen.
"""

from __future__ import annotations

from pathlib import Path

from shared.ingestion import resolve_ingestion_setup
from shared.models.operation import (
    CsvSourceFormat,
    ExcelSourceFormat,
    JsonSourceFormat,
    SourceFormat,
)
from shared.models.source import SourceRef
from shared.storage.probe import read_source_probe
from shared.storage.s3 import download_s3_temp, s3_ref

from suggestion.constants import FILE_SAMPLE_BYTES, JSON_FIRST_OBJECT_MAX_BYTES
from suggestion.source.csv import read_csv_column_names_and_inference_rows, read_csv_sample_rows
from suggestion.source.excel import assemble_excel_reading, read_excel_raw_rows
from suggestion.source.json import (
    ensure_json_first_object_within_limit,
    read_json_column_names_and_inference_rows,
    read_json_sample_rows,
)
from suggestion.source.reading import SourceReading


def read_under_format(source: SourceRef, source_format: SourceFormat) -> SourceReading:
    """Parse one source under a format already resolved, by either strategy."""
    if isinstance(source_format, CsvSourceFormat):
        return _read_csv_under_format(source, source_format)
    if isinstance(source_format, ExcelSourceFormat):
        return _read_excel_under_format(source, source_format)
    if isinstance(source_format, JsonSourceFormat):
        return _read_json_under_format(source, source_format)
    raise TypeError(f"Unsupported source format: {type(source_format).__name__}")


def _read_csv_under_format(source: SourceRef, source_format: CsvSourceFormat) -> SourceReading:
    sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
    text = sample_bytes.decode(source_format.encoding, errors="ignore")
    column_names, inference_rows, discarded = read_csv_column_names_and_inference_rows(
        text,
        delimiter=source_format.delimiter,
        header_mode=source_format.header_mode,
        header_row_index=source_format.header_row_index,
    )
    setup = resolve_ingestion_setup(source, source_format)
    return SourceReading(
        source_format=source_format,
        sample_rows=read_csv_sample_rows(text, source_format.delimiter),
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=setup.url,
        ingestion_source_type=setup.source_type,
        cleanup_path=setup.cleanup_path,
        discarded_row_count=discarded,
        is_sample_based=source.sample is not None,
    )


def _load_excel_rows(source: SourceRef) -> tuple[str, list[tuple[object, ...]]]:
    """Load (sheet_name, all_rows), cleaning up any S3 temp file immediately.

    Rows are fully materialized in memory here, so nothing downstream needs the
    file itself afterward. Excel is never sample-based (a truncated .xlsx cannot
    be opened at all), so a real source_file is always present here.
    """
    if source.source_file is None:
        raise ValueError("Excel source has no source_file; it cannot be read from a sample.")
    if source.source_type == "s3":
        temp_path = download_s3_temp(s3_ref(source.source_file))
        try:
            return read_excel_raw_rows(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
    return read_excel_raw_rows(Path(source.source_file))


def _read_excel_under_format(source: SourceRef, source_format: ExcelSourceFormat) -> SourceReading:
    if source.source_file is None:
        raise ValueError("Excel source has no source_file; it cannot be read from a sample.")
    sheet_name, all_rows = _load_excel_rows(source)
    resolved, sample_rows, column_names, inference_rows = assemble_excel_reading(
        sheet_name, all_rows, source_format.header_mode, source_format.header_row_index
    )
    return SourceReading(
        source_format=resolved,
        sample_rows=sample_rows,
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=source.source_file,
        ingestion_source_type="local",
        cleanup_path=None,
    )


def _read_json_under_format(source: SourceRef, source_format: JsonSourceFormat) -> SourceReading:
    sample_bytes = read_source_probe(source, FILE_SAMPLE_BYTES)
    ensure_json_first_object_within_limit(sample_bytes[:JSON_FIRST_OBJECT_MAX_BYTES])
    column_names, inference_rows = read_json_column_names_and_inference_rows(sample_bytes)
    setup = resolve_ingestion_setup(source, source_format)
    return SourceReading(
        source_format=source_format,
        sample_rows=read_json_sample_rows(sample_bytes),
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=setup.url,
        ingestion_source_type=setup.source_type,
        cleanup_path=setup.cleanup_path,
        is_sample_based=source.sample is not None,
    )
