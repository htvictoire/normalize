"""Runtime source-access contracts shared across app layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.models.base import MainModel
from shared.models.operation import FileFormat, FileSource, SourceFormat


class SourceRef(MainModel):
    """Canonical source identity carried across lifecycle boundaries."""

    source_file: str
    source_type: FileSource
    source_file_name: str
    source_file_format: FileFormat


@dataclass(frozen=True)
class PreparedIngestionSource:
    """Runtime ingestion target resolved from one canonical source."""

    source_url: str
    source_type: FileSource
    cleanup_path: Path | None


@dataclass(frozen=True)
class SourceReading:
    """Stage 1+2 suggestion output."""

    source_format: SourceFormat
    sample_rows: list[list[str]]
    prepared_ingestion: PreparedIngestionSource


__all__ = ["PreparedIngestionSource", "SourceReading", "SourceRef"]
