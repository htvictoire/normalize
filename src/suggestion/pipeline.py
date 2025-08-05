"""Suggestion pipeline composition over inference/profiling components."""

from __future__ import annotations

from pathlib import Path

from shared.db.duckdb import DuckDBManager
from shared.db.sql import read_columns
from shared.ingestion import HeaderMode, IngestionRequest, run_ingestion
from shared.ingestion.checksum import sha256_stream
from shared.utils.column_positions import build_position_to_name
from shared.utils.source_format import infer_source_format
from suggestion.column_config_builder import build_suggested_column_config
from suggestion.inference.sampler import infer_types_from_sample
from suggestion.models import SuggestionOutput
from suggestion.profiling import compute_profiling_stats


def run_suggestion(file_path: str | Path) -> SuggestionOutput:
    """Run suggestion pipeline for one source file."""
    source_file = Path(file_path)
    if not source_file.exists():
        raise FileNotFoundError(f"CSV file not found: {source_file}")

    source = infer_source_format(source_file)
    source_checksum = sha256_stream(source_file)

    with DuckDBManager() as conn:
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

        columns = read_columns(conn, "raw_input")
        position_to_name = build_position_to_name(columns)
        (
            inferred_types,
            inferred_date_formats,
            inferred_numeric_suggestions,
        ) = infer_types_from_sample(conn, table_name="raw_input", columns=columns)
        suggested_column_config = build_suggested_column_config(
            inferred_types=inferred_types,
            inferred_date_formats=inferred_date_formats,
            inferred_numeric_suggestions=inferred_numeric_suggestions,
            position_to_name=position_to_name,
        )
        profiling_stats = compute_profiling_stats(
            conn,
            table_name="raw_input",
            position_to_name=position_to_name,
        )

    return SuggestionOutput(
        source_format=source,
        source_checksum=source_checksum,
        column_labels=position_to_name,
        suggested_column_config=suggested_column_config,
        profiling_stats=profiling_stats,
    )
