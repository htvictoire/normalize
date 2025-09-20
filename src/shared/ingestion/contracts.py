"""
Typed contracts for ingestion execution.

Design notes:
- Keep contracts immutable (`frozen=True`) so stage execution remains
  deterministic and easy to reason about.
- Keep request shape explicit so configuration is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from duckdb import DuckDBPyConnection

from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, FileSource, JsonSourceFormat


class HeaderMode(StrEnum):
    """
    How CSV header handling is configured for one input.

    `PRESENT`:
    File contains headers at `header_row_index`.

    `ABSENT`:
    File has no header row; generated column names are used.
    """

    PRESENT = "present"
    ABSENT = "absent"


@dataclass(frozen=True)
class IngestionRequest:
    """
    Input contract for `run_ingestion`.

    Core inputs:
    - `conn`: active DuckDB connection.
    - `source_url`: source file URL or local path (CSV, Excel, or JSON).
    - `source_type`: whether the source is a local file or S3-compatible object.
    - `source_format`: format-specific settings controlling how the file is read.

    Loading behavior:
    - `table_name`: destination DuckDB table.
    """

    conn: DuckDBPyConnection
    source_url: str
    source_type: FileSource
    source_format: CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat
    table_name: str = "raw_input"


@dataclass(frozen=True)
class IngestionResult:
    """
    Output contract for ingestion execution.

    Includes data-shape metadata (`column_names`) and operational
    metadata (`duration_seconds`, `file_size_bytes`) for tracing.
    `file_size_bytes` is None when the source is a remote object.
    """

    column_names: list[str]
    file_size_bytes: int | None
    table_name: str
    duration_seconds: float
