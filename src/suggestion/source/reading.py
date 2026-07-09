"""The resolved-source-reading contract shared by every inference strategy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.models.operation import FileSource, SourceFormat


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
