"""
Ingestion service entrypoint.

Operational flow:
1. Resolve file size for local sources (not available for remote objects)
2. Dispatch to format-specific ingestor (CSV / Excel / JSON)
3. Return result metadata for metrics and tracing
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from shared.db.duckdb import configure_duckdb_s3
from shared.ingestion.contracts import (
    HeaderMode,
    IngestionRequest,
    IngestionResult,
)
from shared.ingestion.csv.loader import DirectCsvIngestor
from shared.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
)
from shared.ingestion.excel.loader import DirectExcelIngestor
from shared.ingestion.json.loader import DirectJsonIngestor
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat


def run_ingestion(request: IngestionRequest) -> IngestionResult:
    """Dispatch to the format-specific ingestor and return result metadata."""
    start_time = perf_counter()

    file_size_bytes: int | None = None
    if request.source_type == "local":
        file_size_bytes = Path(request.source_url).stat().st_size
    else:
        configure_duckdb_s3(request.conn)

    if isinstance(request.source_format, CsvSourceFormat):
        fmt = request.source_format
        _, load_encoding = resolve_encoding_option(fmt.encoding)
        delimiter = resolve_delimiter_option(fmt.delimiter)
        column_names = DirectCsvIngestor().run(
            request.conn,
            request.source_url,
            table_name=request.table_name,
            encoding=load_encoding,
            delimiter=delimiter,
            header_mode=HeaderMode(fmt.header_mode),
            header_row_index=fmt.header_row_index,
        )
    elif isinstance(request.source_format, ExcelSourceFormat):
        excel_fmt = request.source_format
        column_names = DirectExcelIngestor().run(
            request.conn,
            request.source_url,
            table_name=request.table_name,
            sheet_name=excel_fmt.sheet_name,
            header_mode=HeaderMode(excel_fmt.header_mode),
            header_row_index=excel_fmt.header_row_index,
        )
    else:
        column_names = DirectJsonIngestor().run(
            request.conn,
            request.source_url,
            table_name=request.table_name,
        )

    return IngestionResult(
        column_names=column_names,
        file_size_bytes=file_size_bytes,
        table_name=request.table_name,
        duration_seconds=perf_counter() - start_time,
    )
