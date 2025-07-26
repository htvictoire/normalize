"""
Ingestion service entrypoint.

Operational flow:
1. Resolve input file metadata
2. Validate explicit CSV parse options (encoding + delimiter + header)
3. Execute DuckDB CSV ingestion
4. Compute SHA256 checksum (after DuckDB; hits OS page cache at memory speed)
5. Return rich metadata for metrics, tracing, and manifest construction
"""

from __future__ import annotations

from time import perf_counter

from shared.ingestion.checksum import sha256_stream
from shared.ingestion.contracts import (
    IngestionRequest,
    IngestionResult,
)
from shared.ingestion.csv.loader import DirectCsvIngestor
from shared.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
)


def run_ingestion(request: IngestionRequest) -> IngestionResult:
    """
    Execute ingestion then checksum.

    SHA256 runs after DuckDB has read the CSV so it operates on OS page-cached
    data at memory speed rather than competing for disk bandwidth with DuckDB.
    The background profiling task also reads the same file, so avoiding a third
    concurrent reader reduces I/O contention on large files.
    """
    start_time = perf_counter()
    file_size_bytes = request.csv_path.stat().st_size
    display_encoding, load_encoding = resolve_encoding_option(request.encoding)
    delimiter = resolve_delimiter_option(request.delimiter)

    column_names = DirectCsvIngestor().run(
        request.conn,
        request.csv_path,
        table_name=request.table_name,
        encoding=load_encoding,
        delimiter=delimiter,
        header_mode=request.header_mode,
        header_row_index=request.header_row_index,
    )

    # DuckDB has now read the full file; SHA256 mostly hits OS page cache.
    checksum = sha256_stream(request.csv_path, chunk_size=request.checksum_chunk_size)

    return IngestionResult(
        file_checksum=checksum,
        column_names=column_names,
        file_size_bytes=file_size_bytes,
        encoding=display_encoding,
        delimiter=delimiter,
        table_name=request.table_name,
        duration_seconds=perf_counter() - start_time,
    )
