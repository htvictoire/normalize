"""Exact row count and null counts per column via a single full-source scan."""

from __future__ import annotations

from pathlib import PurePosixPath

import duckdb

from shared.db.duckdb import DuckDBManager, configure_duckdb_s3
from shared.db.sql import compute_column_counts_from_relation
from shared.errors import SourceError
from shared.ingestion.contracts import HeaderMode
from shared.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
    resolve_header_options,
)
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat, JsonSourceFormat
from shared.models.profiling import ColumnCountResult, ColumnCounts

from suggestion.source import SourceReading


def compute_source_stats(
    reading: SourceReading,
    null_tokens: tuple[str, ...],
    position_to_name: dict[str, str],
) -> ColumnCountResult:
    """Return exact (row_count, column_counts) without materializing a table."""
    if not position_to_name:
        name = PurePosixPath(reading.ingestion_source_url).name
        raise SourceError(f"{name!r} contains no columns.")

    if isinstance(reading.source_format, ExcelSourceFormat):
        return _excel_stats(reading, null_tokens, position_to_name)
    if isinstance(reading.source_format, CsvSourceFormat):
        return _scan_stats(
            reading,
            null_tokens,
            position_to_name,
            relation_expr="read_csv(?, header=?, skip=?, delim=?, encoding=?, all_varchar=true)",
            extra_params=_csv_params(reading.source_format),
        )
    if isinstance(reading.source_format, JsonSourceFormat):
        return _scan_stats(
            reading,
            null_tokens,
            position_to_name,
            relation_expr="read_json_auto(?)",
            extra_params=[],
        )
    raise TypeError(f"Unsupported source format: {type(reading.source_format).__name__}")


def _csv_params(fmt: CsvSourceFormat) -> list[object]:
    _, load_encoding = resolve_encoding_option(fmt.encoding)
    delimiter = resolve_delimiter_option(fmt.delimiter)
    header, skip = resolve_header_options(HeaderMode(fmt.header_mode), fmt.header_row_index)
    return [header, skip, delimiter, load_encoding]


def _scan_stats(
    reading: SourceReading,
    null_tokens: tuple[str, ...],
    position_to_name: dict[str, str],
    relation_expr: str,
    extra_params: list[object],
) -> ColumnCountResult:
    """Scan the source through DuckDB.

    This is where DuckDB first parses the whole file, so a file it cannot parse — ragged
    field counts, an undetectable dialect — surfaces here. Those are defects in the
    source, not in the pipeline, and are reported to the caller as such.
    """
    params = [reading.ingestion_source_url, *extra_params]

    with DuckDBManager() as conn:
        if reading.ingestion_source_type == "s3":
            configure_duckdb_s3(conn)
        try:
            return compute_column_counts_from_relation(
                conn,
                relation_expr,
                position_to_name,
                null_tokens,
                params,
            )
        except duckdb.Error as exc:
            name = PurePosixPath(reading.ingestion_source_url).name
            raise SourceError(
                f"Cannot parse {name!r} with the detected format: {_first_line(exc)}"
            ) from exc


def _first_line(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0]


def _excel_stats(
    reading: SourceReading,
    null_tokens: tuple[str, ...],
    position_to_name: dict[str, str],
) -> ColumnCountResult:
    row_count = len(reading.inference_rows)
    null_token_set = set(null_tokens)
    positions = list(position_to_name.keys())
    null_counts: dict[str, int] = dict.fromkeys(positions, 0)
    nullish_counts: dict[str, int] = dict.fromkeys(positions, 0)
    for row in reading.inference_rows:
        for i, pos in enumerate(positions):
            raw = row[i].strip()
            if not raw:
                null_counts[pos] += 1
                nullish_counts[pos] += 1
            elif raw.lower() in null_token_set:
                nullish_counts[pos] += 1
    return ColumnCountResult(
        row_count=row_count,
        column_counts={
            pos: ColumnCounts(
                null_count=null_counts[pos],
                nullish_count=nullish_counts[pos],
                non_null_count=row_count - null_counts[pos],
                non_nullish_count=row_count - nullish_counts[pos],
            )
            for pos in positions
        },
    )
