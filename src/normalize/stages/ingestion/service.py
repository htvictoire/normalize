"""
Ingestion service entrypoint.

Operational flow:
1. Resolve input file metadata
2. Start checksum in background thread
3. Validate explicit CSV parse options (encoding + delimiter + header)
4. Execute DuckDB CSV ingestion (overlaps with checksum I/O)
5. Collect checksum result
6. Return rich metadata for metrics, tracing, and manifest construction
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from normalize.stages.ingestion.checksum import sha256_stream
from normalize.stages.ingestion.contracts import (
    IngestionRequest,
    IngestionResult,
)
from normalize.stages.ingestion.csv.loader import DirectCsvIngestor
from normalize.stages.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
)


def run_ingestion(request: IngestionRequest) -> IngestionResult:
    """
    Execute ingestion with parallel checksum.

    SHA256 hashing runs in a background thread while DuckDB reads the CSV,
    overlapping I/O to reduce wall-clock time.
    """
    start_time = perf_counter()
    file_size_bytes = request.csv_path.stat().st_size
    display_encoding, load_encoding = resolve_encoding_option(request.encoding)
    delimiter = resolve_delimiter_option(request.delimiter)

    # Start checksum in background — both reads are sequential I/O on the same
    # file, but OS page cache means the second reader mostly hits warm pages.
    with ThreadPoolExecutor(max_workers=1) as pool:
        checksum_future = pool.submit(
            sha256_stream, request.csv_path, chunk_size=request.checksum_chunk_size
        )

        row_count, column_names = DirectCsvIngestor().run(
            request.conn,
            request.csv_path,
            table_name=request.table_name,
            encoding=load_encoding,
            delimiter=delimiter,
            header_mode=request.header_mode,
            header_row_index=request.header_row_index,
        )

        checksum = checksum_future.result()

    return IngestionResult(
        file_checksum=checksum,
        row_count=row_count,
        column_names=column_names,
        file_size_bytes=file_size_bytes,
        encoding=display_encoding,
        delimiter=delimiter,
        table_name=request.table_name,
        duration_seconds=perf_counter() - start_time,
    )
