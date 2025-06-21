"""Background ThreadPoolExecutor target functions for pipeline optimizations."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

import duckdb as _duckdb

from normalize.core.numeric_formats import NumericFormat
from normalize.core.sql_helpers import quote_identifier, read_columns
from normalize.core.token_policy import TokenPolicy
from normalize.stages.artifact_materialization.export import (
    write_normalized_parquet,
)
from normalize.stages.artifact_materialization.trace import write_trace_parquet
from normalize.stages.header_canonicalization import canonicalize_header_sequence
from normalize.stages.ingestion.contracts import HeaderMode
from normalize.stages.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
    resolve_header_options,
)
from normalize.stages.shared_profiling import (
    ColumnProfile,
    compute_and_store_column_profiles,
)


def run_profiling_background(
    csv_path: Path,
    header_mode: HeaderMode,
    header_row_index: int | None,
    encoding: str,
    delimiter: str,
    token_policy: TokenPolicy,
    decimal_separator: str,
    thousand_separator: str,
    grouping_style: str,
    numeric_formats: dict[str, NumericFormat] | None,
    allow_leading_decimal_point: bool,
    currency_candidate_threshold: float,
) -> dict[str, ColumnProfile]:
    """Run column profiling on a separate in-memory DuckDB connection.

    Loads the same CSV independently, canonicalizes headers with pure-Python
    logic, and runs the one-pass profiling query.  Returns the profiles dict
    for the caller to store on the main connection.
    """
    header, skip = resolve_header_options(header_mode, header_row_index)
    _, load_encoding = resolve_encoding_option(encoding)
    resolved_delimiter = resolve_delimiter_option(delimiter)

    conn = _duckdb.connect(":memory:")
    try:
        conn.execute(
            "CREATE TABLE _prof AS "
            "SELECT * FROM read_csv(?, header=?, skip=?, delim=?, encoding=?, all_varchar=true)",
            [str(csv_path), header, skip, resolved_delimiter, load_encoding],
        )

        columns = read_columns(conn, "_prof")
        canonical_columns = canonicalize_header_sequence(columns)
        rename_pairs = [
            (raw, canon)
            for raw, canon in zip(columns, canonical_columns, strict=False)
            if raw != canon
        ]
        if rename_pairs:
            conn.execute("BEGIN TRANSACTION")
            try:
                for raw, canon in rename_pairs:
                    conn.execute(
                        f"ALTER TABLE _prof RENAME COLUMN "
                        f"{quote_identifier(raw)} TO {quote_identifier(canon)}"
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return compute_and_store_column_profiles(
            conn,
            table_name="_prof",
            token_policy=token_policy,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
            numeric_formats=numeric_formats,
            allow_leading_decimal_point=allow_leading_decimal_point,
            currency_candidate_threshold=currency_candidate_threshold,
        )
    finally:
        conn.close()


def write_parquets_background(
    db_path: str,
    output_root: Path,
    fingerprint: str,
    trace_mode: str,
    table_name: str,
    export_columns: list[str],
    data_columns: list[str],
    table_columns: list[str],
) -> dict[str, float]:
    """Write parquet files on a second connection to the file-backed DB.

    Opens a separate connection (same config as the main writer) so COPY-TO
    can run concurrently with read-only quality-metrics work on the main
    connection.  Returns a timing dict with section durations.
    """
    timing: dict[str, float] = {}
    conn = _duckdb.connect(db_path)
    try:
        normalized_path = output_root / f"{fingerprint}.parquet"
        trace_path = output_root / f"{fingerprint}.trace.parquet"

        section_start = perf_counter()
        write_normalized_parquet(
            conn,
            normalized_path=normalized_path,
            table_name=table_name,
            export_columns=export_columns,
        )
        timing["write_normalized_parquet_seconds"] = perf_counter() - section_start

        section_start = perf_counter()
        sparse = trace_mode == "sparse"
        trace_pre_filter: str | None = None
        if sparse and "_parse_error_count" in table_columns:
            trace_pre_filter = "_parse_error_count > 0"
        write_trace_parquet(
            conn,
            trace_path=trace_path,
            table_name=table_name,
            data_columns=data_columns,
            table_columns=table_columns,
            sparse=sparse,
            row_pre_filter=trace_pre_filter,
        )
        timing["write_trace_parquet_seconds"] = perf_counter() - section_start

        return timing
    finally:
        conn.close()
