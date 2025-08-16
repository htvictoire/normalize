"""Suggestion pipeline — orchestrates stages in order."""

from __future__ import annotations

from pathlib import Path

from shared.db.duckdb import DuckDBManager
from shared.db.sql import read_columns
from shared.ingestion import HeaderMode, IngestionRequest, run_ingestion
from shared.models.suggestion import SuggestedColumn, SuggestionOutput
from shared.utils.column_positions import build_position_to_name
from suggestion.column_types.builder import build_suggested_column_config
from suggestion.column_types.sampler import infer_types_from_sample
from suggestion.null_counts import compute_null_counts
from suggestion.sample_data import read_sample_rows, read_sample_values
from suggestion.constants import FILE_SAMPLE_BYTES
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

        # Stage 4 — derive column labels
        columns = read_columns(conn, "raw_input")
        position_to_name = build_position_to_name(columns)

        # Stage 5 — infer column types from sampled rows
        inferred_types, inferred_date_formats, inferred_numeric_suggestions = (
            infer_types_from_sample(conn, table_name="raw_input", columns=columns)
        )
        suggested_column_config = build_suggested_column_config(
            inferred_types=inferred_types,
            inferred_date_formats=inferred_date_formats,
            inferred_numeric_suggestions=inferred_numeric_suggestions,
            position_to_name=position_to_name,
        )

        # Stage 6 — compute null counts over full table
        row_count, null_counts = compute_null_counts(
            conn,
            table_name="raw_input",
            position_to_name=position_to_name,
        )

        # Stage 7 — collect per-column sample values for display
        sample_values_by_position = read_sample_values(
            conn,
            table_name="raw_input",
            position_to_name=position_to_name,
        )

    return SuggestionOutput(
        source_format=source,
        row_count=row_count,
        columns={
            pos: SuggestedColumn(
                label=position_to_name[pos],
                config=suggested_column_config[pos],
                null_count=null_counts.get(pos, (0, 0))[0],
                non_null_count=null_counts.get(pos, (0, 0))[1],
                sample_values=sample_values_by_position.get(pos, []),
            )
            for pos in position_to_name
        },
        sample_rows=sample_rows,
    )
