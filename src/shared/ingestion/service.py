"""
Ingestion service entrypoint.

Operational flow:
1. Resolve input file metadata
2. Dispatch to format-specific ingestor (CSV / Excel / JSON)
3. Compute SHA256 checksum (after ingestor; hits OS page cache at memory speed)
4. Return rich metadata for metrics, tracing, and manifest construction
"""

from __future__ import annotations

from time import perf_counter

from shared.ingestion.checksum import sha256_stream
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
    """
    Execute ingestion then checksum.

    SHA256 runs after the ingestor has read the file so it operates on
    OS page-cached data at memory speed rather than competing for disk
    bandwidth with the ingestor.
    """
    start_time = perf_counter()
    file_size_bytes = request.source_path.stat().st_size

    if isinstance(request.source_format, CsvSourceFormat):
        fmt = request.source_format
        _, load_encoding = resolve_encoding_option(fmt.encoding)
        delimiter = resolve_delimiter_option(fmt.delimiter)
        column_names = DirectCsvIngestor().run(
            request.conn,
            request.source_path,
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
            request.source_path,
            table_name=request.table_name,
            sheet_name=excel_fmt.sheet_name,
            header_mode=HeaderMode(excel_fmt.header_mode),
            header_row_index=excel_fmt.header_row_index,
        )
    else:
        column_names = DirectJsonIngestor().run(
            request.conn,
            request.source_path,
            table_name=request.table_name,
        )

    checksum = sha256_stream(request.source_path, chunk_size=request.checksum_chunk_size)

    return IngestionResult(
        file_checksum=checksum,
        column_names=column_names,
        file_size_bytes=file_size_bytes,
        table_name=request.table_name,
        duration_seconds=perf_counter() - start_time,
    )
