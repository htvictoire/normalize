"""
Pipeline ingestion stage adapter.

This stage intentionally contains no file-loading implementation details.
It delegates to `shared.ingestion` package so ingestion behavior
can evolve without changing stage orchestration contracts.
"""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.ingestion.contracts import (
    IngestionRequest,
    IngestionResult,
)
from shared.ingestion.service import run_ingestion
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, FileSource, JsonSourceFormat
from shared.stage import Stage


class IngestionStage(Stage):
    """
    Stage adapter that routes ingestion through the ingestion package.

    Stage-level concerns:
    - enforce explicit parse configuration via source format
    - map ingestion result into standard stage metrics
    """

    def __init__(self, *, table_name: str = "raw_input") -> None:
        super().__init__()
        self._table_name = table_name

    def execute(
        self,
        conn: DuckDBPyConnection,
        source_url: str,
        *,
        source_type: FileSource,
        source_format: CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat,
    ) -> IngestionResult:
        """
        Execute ingestion and expose stage metrics.

        Returns:
        - `IngestionResult` produced by ingestion service
        """
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                source_url=source_url,
                source_type=source_type,
                source_format=source_format,
                table_name=self._table_name,
            )
        )
        self.metrics = {
            "duration_seconds": result.duration_seconds,
            "column_count": len(result.column_names),
            "file_size_bytes": result.file_size_bytes or 0,
            "format_type": source_format.format_type,
        }
        return result
