"""Source reading orchestration for the suggestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.models.operation import FileSource, SourceFormat
from shared.models.source import SourceRef
from shared.storage.probe import read_source_probe
from shared.storage.s3 import build_duckdb_s3_url, download_s3_temp, s3_ref

from suggestion.constants import FILE_SAMPLE_BYTES, JSON_FIRST_OBJECT_MAX_BYTES
from suggestion.source.csv import (
    infer_csv_source_format,
    read_csv_column_names_and_inference_rows,
    read_csv_sample_rows,
)
from suggestion.source.excel import read_excel_source
from suggestion.source.json import (
    ensure_json_first_object_within_limit,
    infer_json_source_format,
    read_json_column_names_and_inference_rows,
    read_json_sample_rows,
)


@dataclass(frozen=True)
class SourceReading:
    """Inferred format, raw sample rows, column names, inference rows, and ingestion target."""

    source_format: SourceFormat
    sample_rows: list[list[str]]
    column_names: list[str]
    inference_rows: list[list[str]]
    ingestion_source_url: str
    ingestion_source_type: FileSource
    cleanup_path: Path | None


def _read_csv_source(source: SourceRef) -> SourceReading:
    sample = read_source_probe(source, FILE_SAMPLE_BYTES)
    source_format = infer_csv_source_format(sample)
    text = sample.decode(source_format.encoding, errors="ignore")
    sample_rows = read_csv_sample_rows(text, delimiter=source_format.delimiter)
    column_names, inference_rows = read_csv_column_names_and_inference_rows(
        text,
        delimiter=source_format.delimiter,
        header_mode=source_format.header_mode,
        header_row_index=source_format.header_row_index,
    )
    if source.source_type == "s3":
        ingestion_url = build_duckdb_s3_url(s3_ref(source.source_file))
    else:
        ingestion_url = source.source_file
    return SourceReading(
        source_format=source_format,
        sample_rows=sample_rows,
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=ingestion_url,
        ingestion_source_type=source.source_type,
        cleanup_path=None,
    )


def _read_excel_source(source: SourceRef) -> SourceReading:
    if source.source_type == "s3":
        temp_path = download_s3_temp(s3_ref(source.source_file))
        ingestion_url = str(temp_path)
        cleanup_path: Path | None = temp_path
    else:
        ingestion_url = source.source_file
        cleanup_path = None
    try:
        source_format, sample_rows, column_names, inference_rows = read_excel_source(
            Path(ingestion_url)
        )
    except Exception:
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)
        raise
    return SourceReading(
        source_format=source_format,
        sample_rows=sample_rows,
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=ingestion_url,
        ingestion_source_type="local",
        cleanup_path=cleanup_path,
    )


def _read_json_source(source: SourceRef) -> SourceReading:
    sample = read_source_probe(source, FILE_SAMPLE_BYTES)
    ensure_json_first_object_within_limit(sample[:JSON_FIRST_OBJECT_MAX_BYTES])
    if source.source_type == "s3":
        ingestion_url = build_duckdb_s3_url(s3_ref(source.source_file))
    else:
        ingestion_url = source.source_file
    column_names, inference_rows = read_json_column_names_and_inference_rows(sample)
    return SourceReading(
        source_format=infer_json_source_format(),
        sample_rows=read_json_sample_rows(sample),
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=ingestion_url,
        ingestion_source_type=source.source_type,
        cleanup_path=None,
    )


def read_source(source: SourceRef) -> SourceReading:
    """Infer format settings, collect sample rows, and parse inference rows for one source."""
    if source.source_file_format == "csv":
        return _read_csv_source(source)
    if source.source_file_format == "excel":
        return _read_excel_source(source)
    if source.source_file_format == "json":
        return _read_json_source(source)
    raise ValueError(f"Unsupported source file format: {source.source_file_format!r}")
