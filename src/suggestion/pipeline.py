"""Suggestion pipeline — orchestrates stages in order."""

from __future__ import annotations

from pathlib import Path

from shared.db.duckdb import DuckDBManager
from shared.db.sql import compute_column_counts, read_columns
from shared.ingestion import IngestionRequest, run_ingestion
from shared.models.operation import CsvSourceFormat, FileFormat
from shared.models.suggestion import SuggestedColumn, SuggestionOutput
from shared.utils.column import build_position_to_name
from suggestion.column_config import infer_column_type, sample_column_values
from suggestion.null_tokens import infer_null_tokens
from suggestion.sample_data import (
    read_csv_sample_rows,
    read_excel_sample_rows,
    read_json_sample_rows,
    read_sample_values,
)
from suggestion.source_format import infer_source_format


def run_suggestion(file_path: str | Path, *, format_type: FileFormat) -> SuggestionOutput:
    """Run suggestion pipeline for one source file."""
    source_file = Path(file_path)
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    # Stage 1 — infer source format from file content
    source = infer_source_format(source_file, format_type)

    # Stage 2 — read raw sample rows directly from file for display
    if isinstance(source, CsvSourceFormat):
        raw_bytes = source_file.read_bytes()
        decoded = raw_bytes.decode(source.encoding, errors="ignore")
        sample_rows = read_csv_sample_rows(decoded, delimiter=source.delimiter)
    elif format_type == "excel":
        sample_rows = read_excel_sample_rows(source_file)
    else:
        sample_rows = read_json_sample_rows(source_file)

    with DuckDBManager() as conn:
        # Stage 3 — ingest into DuckDB
        run_ingestion(
            IngestionRequest(
                conn=conn,
                source_path=source_file,
                source_format=source,
                table_name="raw_input",
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
