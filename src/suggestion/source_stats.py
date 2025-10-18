"""Exact row count and null counts per column via a single full-source scan."""

from __future__ import annotations

from shared.db.duckdb import DuckDBManager, configure_duckdb_s3
from shared.db.sql import nullish_predicate, quote_identifier
from shared.ingestion.contracts import HeaderMode
from shared.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
    resolve_header_options,
)
from shared.models.operation import CsvSourceFormat, ExcelSourceFormat
from shared.models.profiling import ColumnCounts
from suggestion.source.read import SourceReading


def compute_source_stats(
    reading: SourceReading,
    null_tokens: tuple[str, ...],
    position_to_name: dict[str, str],
) -> tuple[int, dict[str, ColumnCounts]]:
    """Return exact (row_count, column_counts) without materializing a table."""
    if isinstance(reading.source_format, ExcelSourceFormat):
        return _excel_stats(reading, null_tokens, position_to_name)
    if isinstance(reading.source_format, CsvSourceFormat):
        return _scan_stats(
            reading,
            null_tokens,
            position_to_name,
            source_expr="read_csv(?, header=?, skip=?, delim=?, encoding=?, all_varchar=true)",
            extra_params=_csv_params(reading.source_format),
        )
    return _scan_stats(
        reading,
        null_tokens,
        position_to_name,
        source_expr="read_json_auto(?)",
        extra_params=[],
    )


def _csv_params(fmt: CsvSourceFormat) -> list[object]:
    _, load_encoding = resolve_encoding_option(fmt.encoding)
    delimiter = resolve_delimiter_option(fmt.delimiter)
    header, skip = resolve_header_options(HeaderMode(fmt.header_mode), fmt.header_row_index)
    return [header, skip, delimiter, load_encoding]


def _scan_stats(
    reading: SourceReading,
    null_tokens: tuple[str, ...],
    position_to_name: dict[str, str],
    *,
    source_expr: str,
    extra_params: list[object],
) -> tuple[int, dict[str, ColumnCounts]]:
    exprs: list[str] = []
    for index, column_name in enumerate(position_to_name.values()):
        quoted = quote_identifier(column_name)
        structural = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '') IS NULL"
        nullish = nullish_predicate(quoted, null_tokens)
        exprs.append(
            f"COALESCE(SUM(CASE WHEN {structural} THEN 1 ELSE 0 END), 0) AS __c{index}_null"
        )
        exprs.append(
            f"COALESCE(SUM(CASE WHEN {nullish} THEN 1 ELSE 0 END), 0) AS __c{index}_nullish"
        )

    query = f"SELECT COUNT(*) AS __row_count, {', '.join(exprs)} FROM {source_expr}"
    params = [reading.ingestion_source_url, *extra_params]

    with DuckDBManager() as conn:
        if reading.ingestion_source_type == "s3":
            configure_duckdb_s3(conn)
        row = conn.execute(query, params).fetchall()[0]

    row_count = int(row[0])
    counts: dict[str, ColumnCounts] = {}
    for index, pos in enumerate(position_to_name.keys()):
        null_count = int(row[1 + index * 2])
        nullish_count = int(row[1 + index * 2 + 1])
        counts[pos] = ColumnCounts(
            null_count=null_count,
            nullish_count=nullish_count,
            non_null_count=row_count - null_count,
            non_nullish_count=row_count - nullish_count,
        )
    return row_count, counts


def _excel_stats(
    reading: SourceReading,
    null_tokens: tuple[str, ...],
    position_to_name: dict[str, str],
) -> tuple[int, dict[str, ColumnCounts]]:
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
    return row_count, {
        pos: ColumnCounts(
            null_count=null_counts[pos],
            nullish_count=nullish_counts[pos],
            non_null_count=row_count - null_counts[pos],
            non_nullish_count=row_count - nullish_counts[pos],
        )
        for pos in positions
    }
