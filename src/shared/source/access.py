"""Shared helpers for source probing and ingestion preparation."""

from __future__ import annotations

from pathlib import Path

from shared.models.operation import FileFormat, SourceFormat
from shared.models.source import PreparedIngestionSource, SourceRef
from shared.settings import get_settings
from shared.storage.s3 import (
    S3ObjectRef,
    build_duckdb_s3_url,
    download_s3_temp,
    fetch_s3_probe,
)


def _resolve_format_type(source_format: FileFormat | SourceFormat) -> FileFormat:
    """Return the declared format type from a file-format discriminator or source format."""
    if isinstance(source_format, str):
        return source_format
    return source_format.format_type


def _s3_ref(source: SourceRef) -> S3ObjectRef:
    return S3ObjectRef(bucket=get_settings().s3_bucket, key=source.source_file)


def read_source_probe(source: SourceRef, n_bytes: int) -> bytes:
    """Return the first `n_bytes` of the original source."""
    if n_bytes < 1:
        raise ValueError("n_bytes must be >= 1")

    if source.source_type == "s3":
        return fetch_s3_probe(_s3_ref(source), n_bytes)

    with Path(source.source_file).open("rb") as handle:
        return handle.read(n_bytes)


def prepare_ingestion_source(
    source: SourceRef,
    source_format: FileFormat | SourceFormat,
) -> PreparedIngestionSource:
    """Resolve the runtime source target that ingestion should actually read."""
    format_type = _resolve_format_type(source_format)
    if source.source_type == "local":
        return PreparedIngestionSource(
            source_url=source.source_file,
            source_type="local",
            cleanup_path=None,
        )

    obj = _s3_ref(source)
    if format_type == "excel":
        temp_path = download_s3_temp(obj)
        return PreparedIngestionSource(
            source_url=str(temp_path),
            source_type="local",
            cleanup_path=temp_path,
        )

    return PreparedIngestionSource(
        source_url=build_duckdb_s3_url(obj),
        source_type="s3",
        cleanup_path=None,
    )
