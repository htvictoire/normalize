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
from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, JsonSourceFormat


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
    - `source_path`: source file path (CSV, Excel, or JSON).
    - `source_format`: format-specific settings controlling how the file is read.

    Loading behavior:
    - `table_name`: destination DuckDB table.
    - `checksum_chunk_size`: streaming checksum chunk size in bytes.
    """

    conn: DuckDBPyConnection
    source_path: Path
    source_format: CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat
    table_name: str = "raw_input"
    checksum_chunk_size: int = 1_048_576


@dataclass(frozen=True)
class IngestionResult:
    """
    Output contract for ingestion execution.

    Includes both data-shape metadata (`column_names`) and operational
    metadata (`duration_seconds`) so the caller can persist traceable
    run diagnostics.
    """

    file_checksum: str
    column_names: list[str]
    file_size_bytes: int
    table_name: str
    duration_seconds: float
