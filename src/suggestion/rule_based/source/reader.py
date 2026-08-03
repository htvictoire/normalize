"""Source reading orchestration for the rule-based inference strategy.

Resolves a SourceReading by heuristically guessing CSV delimiter/header and
Excel header placement. This is one strategy's approach to reading — it is
not the shared contract itself (see suggestion.source.reading.SourceReading).
"""

from __future__ import annotations

from pathlib import Path

from shared.ingestion import resolve_ingestion_setup
from shared.models.source import SourceRef
from shared.storage.probe import read_source_probe
from shared.storage.s3 import download_s3_temp, s3_ref

from suggestion.constants import FILE_SAMPLE_BYTES, JSON_FIRST_OBJECT_MAX_BYTES
from suggestion.rule_based.source.csv import infer_csv_source_format
from suggestion.rule_based.source.excel import read_excel_source
from suggestion.source.csv import (
    read_csv_column_names_and_inference_rows,
    read_csv_sample_rows,
)
from suggestion.source.json import (
    ensure_json_first_object_within_limit,
    infer_json_source_format,
    read_json_column_names_and_inference_rows,
    read_json_sample_rows,
)
from suggestion.source.reading import SourceReading, effective_file_format


def _read_csv_source(source: SourceRef) -> SourceReading:
    sample = read_source_probe(source, FILE_SAMPLE_BYTES)
    source_format = infer_csv_source_format(sample)
    text = sample.decode(source_format.encoding, errors="ignore")
    sample_rows = read_csv_sample_rows(text, source_format.delimiter)
    column_names, inference_rows, discarded = read_csv_column_names_and_inference_rows(
        text,
        delimiter=source_format.delimiter,
        header_mode=source_format.header_mode,
        header_row_index=source_format.header_row_index,
    )
    setup = resolve_ingestion_setup(source, source_format)
    return SourceReading(
        source_format=source_format,
        sample_rows=sample_rows,
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=setup.url,
        ingestion_source_type=setup.source_type,
        cleanup_path=setup.cleanup_path,
        discarded_row_count=discarded,
        is_sample_based=source.sample is not None,
    )


def _read_excel_source(source: SourceRef) -> SourceReading:
    if source.source_file is None:
        raise ValueError("Excel source has no source_file; it cannot be read from a sample.")
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
    column_names, inference_rows = read_json_column_names_and_inference_rows(sample)
    source_format = infer_json_source_format()
    setup = resolve_ingestion_setup(source, source_format)
    return SourceReading(
        source_format=source_format,
        sample_rows=read_json_sample_rows(sample),
        column_names=column_names,
        inference_rows=inference_rows,
        ingestion_source_url=setup.url,
        ingestion_source_type=setup.source_type,
        cleanup_path=setup.cleanup_path,
        is_sample_based=source.sample is not None,
    )


def read_source(source: SourceRef) -> SourceReading:
    """Infer format settings, collect sample rows, and parse inference rows for one source."""
    fmt = effective_file_format(source)
    if fmt == "csv":
        return _read_csv_source(source)
    if fmt == "excel":
        return _read_excel_source(source)
    if fmt == "json":
        return _read_json_source(source)
    raise ValueError(f"Unsupported source file format: {fmt!r}")
