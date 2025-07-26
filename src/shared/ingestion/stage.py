"""
Pipeline ingestion stage adapter.

This stage intentionally contains no file-loading implementation details.
It delegates to `shared.ingestion` package so ingestion behavior
can evolve without changing stage orchestration contracts.
"""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.ingestion.contracts import (
    HeaderMode,
    IngestionRequest,
    IngestionResult,
)
from shared.ingestion.service import run_ingestion
from shared.stages.base import Stage


class IngestionStage(Stage):
    """
    Stage adapter that routes ingestion through the ingestion package.

    Stage-level concerns:
    - enforce explicit parse configuration (header, encoding, delimiter)
    - map ingestion result into standard stage metrics
    """

    def __init__(self, *, table_name: str = "raw_input") -> None:
        super().__init__()
        self._table_name = table_name

    def execute(
        self,
        conn: DuckDBPyConnection,
        csv_path: str | Path,
        *,
        header_mode: HeaderMode,
        header_row_index: int | None,
        encoding: str,
        delimiter: str,
    ) -> IngestionResult:
        """
        Execute ingestion and expose stage metrics.

        Returns:
        - `IngestionResult` produced by ingestion service
        """
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=Path(csv_path),
                header_mode=header_mode,
                header_row_index=header_row_index,
                encoding=encoding,
                delimiter=delimiter,
                table_name=self._table_name,
            )
        )
        self.metrics = {
            "duration_seconds": result.duration_seconds,
            "column_count": len(result.column_names),
            "file_size_bytes": result.file_size_bytes,
            "encoding": result.encoding,
            "delimiter": result.delimiter,
        }
        return result
