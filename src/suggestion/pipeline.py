"""Suggestion pipeline — orchestrates stages in order."""

from __future__ import annotations

from pathlib import Path

from shared.db.duckdb import DuckDBManager
from shared.db.sql import compute_column_counts, read_columns
from shared.ingestion import HeaderMode, IngestionRequest, run_ingestion
from shared.models.suggestion import SuggestedColumn, SuggestionOutput
from shared.utils.column import build_position_to_name
from suggestion.column_config import infer_column_type, sample_column_values
from suggestion.constants import FILE_SAMPLE_BYTES
from suggestion.null_tokens import infer_null_tokens
from suggestion.sample_data import read_sample_rows, read_sample_values
from suggestion.source_format import infer_source_format_from_bytes


def run_suggestion(file_path: str | Path) -> SuggestionOutput:
    """Run suggestion pipeline for one source file."""
    source_file = Path(file_path)
    if not source_file.exists():
        raise FileNotFoundError(f"CSV file not found: {source_file}")

    # Stage 1 — infer source format
    raw_sample = source_file.read_bytes()[:FILE_SAMPLE_BYTES]
    source = infer_source_format_from_bytes(raw_sample)

    # Stage 2 — get raw sample rows
    decoded_sample = raw_sample.decode(source.encoding, errors="ignore")
    sample_rows = read_sample_rows(decoded_sample, delimiter=source.delimiter)

    with DuckDBManager() as conn:
        # Stage 3 — ingest into DuckDB (using inferred source format settings)
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=source_file,
                table_name="raw_input",
                header_mode=HeaderMode(source.header_mode),
                header_row_index=source.header_row_index,
                encoding=source.encoding,
                delimiter=source.delimiter,
            )
        )

        # Stage 4 — derive column labels and position keys
        columns = read_columns(conn, "raw_input")
        position_to_name = build_position_to_name(columns)

        # Stage 5 — infer column types
        sampled_values = sample_column_values(conn, table_name="raw_input", columns=columns)
        column_configs = {
            pos: infer_column_type(sampled_values[name])
            for pos, name in position_to_name.items()
        }

        # Stage 6 — infer null tokens from data
        null_tokens = infer_null_tokens(conn, table_name="raw_input", columns=columns)

        # Stage 7 — compute null/non-null counts using inferred null tokens
        row_count, column_counts = compute_column_counts(
            conn,
            table_name="raw_input",
            position_to_name=position_to_name,
            null_tokens=null_tokens,
        )

        # Stage 8 — collect per-column sample values for display
        sample_values_by_position = read_sample_values(
            conn,
            table_name="raw_input",
            position_to_name=position_to_name,
        )

    return SuggestionOutput(
        source_format=source,
        null_tokens=null_tokens,
        row_count=row_count,
        columns={
            pos: SuggestedColumn(
                label=position_to_name[pos],
                config=column_configs[pos],
                counts=column_counts[pos],
                sample_values=sample_values_by_position[pos],
            )
            for pos in position_to_name
        },
        sample_rows=sample_rows,
    )
