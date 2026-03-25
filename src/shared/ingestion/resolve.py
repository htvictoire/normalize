"""Shared ingestion source resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.models.operation import ExcelSourceFormat, FileSource, SourceFormat
from shared.models.source import SourceRef
from shared.storage.s3 import build_duckdb_s3_url, download_s3_temp, s3_ref


@dataclass(frozen=True)
class IngestionSetup:
    """Resolved ingestion coordinates for one source file."""

    url: str
    source_type: FileSource
    cleanup_path: Path | None


def resolve_ingestion_setup(source: SourceRef, source_format: SourceFormat) -> IngestionSetup:
    """Resolve the DuckDB ingestion URL and download a temp copy when required."""
    if source.source_type == "s3" and isinstance(source_format, ExcelSourceFormat):
        cleanup_path = download_s3_temp(s3_ref(source.source_file))
        return IngestionSetup(
            url=str(cleanup_path), source_type="local", cleanup_path=cleanup_path
        )
    if source.source_type == "s3":
        return IngestionSetup(
            url=build_duckdb_s3_url(s3_ref(source.source_file)),
            source_type="s3",
            cleanup_path=None,
        )
    return IngestionSetup(url=source.source_file, source_type="local", cleanup_path=None)


def cleanup_ingestion_setup(setup: IngestionSetup) -> None:
    """Remove the temp file created during ingestion setup, if any."""
    if setup.cleanup_path is not None:
        setup.cleanup_path.unlink(missing_ok=True)
