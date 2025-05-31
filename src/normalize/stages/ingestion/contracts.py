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
    - `csv_path`: source CSV path.
    - `header_mode`: explicit header policy (`present` or `absent`).
    - `header_row_index`: 1-based row index when `header_mode=present`.
    - `encoding`: explicit file encoding (no auto-detection).
    - `delimiter`: explicit single-character delimiter (no auto-detection).

    Loading behavior:
    - `table_name`: destination DuckDB table.
    - `checksum_chunk_size`: streaming checksum chunk size in bytes.
    """

    conn: DuckDBPyConnection
    csv_path: Path
    header_mode: HeaderMode
    header_row_index: int | None
    encoding: str
    delimiter: str
    table_name: str = "raw_input"
    checksum_chunk_size: int = 1_048_576


@dataclass(frozen=True)
class IngestionResult:
    """
    Output contract for ingestion execution.

    Includes both data-shape metadata (`row_count`, `column_names`) and
    operational metadata (`duration_seconds`) so the caller can persist
    traceable run diagnostics.
    """

    file_checksum: str
    row_count: int
    column_names: list[str]
    file_size_bytes: int
    encoding: str
    delimiter: str
    table_name: str
    duration_seconds: float
