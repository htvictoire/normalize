"""Suggestion Stage 1+2 source reading orchestration."""

from __future__ import annotations

from pathlib import Path

from shared.models.source import SourceReading, SourceRef
from shared.source.access import prepare_ingestion_source, read_source_probe
from suggestion.constants import FILE_SAMPLE_BYTES
from suggestion.source.csv import infer_csv_source_format, read_csv_sample_rows
from suggestion.source.excel import read_excel_source
from suggestion.source.json import infer_json_source_format, read_json_sample_rows


def _cleanup_temp_file(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def _read_csv_source(source: SourceRef) -> SourceReading:
    sample = read_source_probe(source, FILE_SAMPLE_BYTES)
    source_format = infer_csv_source_format(sample)
    sample_rows = read_csv_sample_rows(
        sample.decode(source_format.encoding, errors="ignore"),
        delimiter=source_format.delimiter,
    )
    return SourceReading(
        source_format=source_format,
        sample_rows=sample_rows,
        prepared_ingestion=prepare_ingestion_source(source, source.source_file_format),
    )


def _read_excel_source(source: SourceRef) -> SourceReading:
    prepared = prepare_ingestion_source(source, source.source_file_format)
    try:
        source_format, sample_rows = read_excel_source(Path(prepared.source_url))
        return SourceReading(
            source_format=source_format,
            sample_rows=sample_rows,
            prepared_ingestion=prepared,
        )
    except Exception:
        _cleanup_temp_file(prepared.cleanup_path)
        raise


def _read_json_source(source: SourceRef) -> SourceReading:
    sample = read_source_probe(source, FILE_SAMPLE_BYTES)
    return SourceReading(
        source_format=infer_json_source_format(),
        sample_rows=read_json_sample_rows(sample),
        prepared_ingestion=prepare_ingestion_source(source, source.source_file_format),
    )


def read_source(source: SourceRef) -> SourceReading:
    """Read suggestion Stage 1+2 data for one source."""
    if source.source_file_format == "csv":
        return _read_csv_source(source)
    if source.source_file_format == "excel":
        return _read_excel_source(source)
    return _read_json_source(source)
