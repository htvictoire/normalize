"""
Suggestion pipeline — infers provisional settings for one source file.

Stage 1  Infer source format from file content: encoding, delimiter, and header
         position for CSV; sheet and header for Excel; no inference needed for JSON.

Stage 2  Read raw sample rows directly from the source file so the display
         reflects exactly what the user submitted before any inferred settings
         are applied.

Stage 3  Ingest into an in-memory DuckDB instance using the inferred format.
         The connection is discarded after Stage 8 — nothing is persisted.

Stage 4  Derive ordered column labels and position keys.

Stage 5  Infer a ColumnConfig (type, separators, date format, …) per column
         from a random sample of up to 256 non-null values.

Stage 6  Infer null tokens from recurring empty-looking values across all columns.

Stage 7  Compute null / non-null counts per column using the inferred null tokens.

Stage 8  Collect per-column sample values for display.
"""

from __future__ import annotations

from shared.db.duckdb import DuckDBManager
from shared.db.sql import compute_column_counts, read_columns
from shared.ingestion import IngestionRequest, run_ingestion
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestedColumn, SuggestionOutput
from shared.utils.column import build_position_to_name
from suggestion.column_config.inference import infer_column_type
from suggestion.column_config.sampler import sample_column_values
from suggestion.null_tokens import infer_null_tokens
from suggestion.column_display import read_sample_values
from suggestion.source.read import read_source


def run_suggestion(source: SourceRef) -> SuggestionOutput:
    """Run suggestion pipeline for one source file."""
    reading = read_source(source)
    try:
        with DuckDBManager() as conn:
            # Stage 3
            run_ingestion(
                IngestionRequest(
                    conn=conn,
                    source_url=reading.prepared_ingestion.source_url,
                    source_type=reading.prepared_ingestion.source_type,
                    source_format=reading.source_format,
                    table_name="raw_input",
                )
            )

            # Stage 4
            columns = read_columns(conn, "raw_input")
            position_to_name = build_position_to_name(columns)

            # Stage 5
            sampled_values = sample_column_values(conn, table_name="raw_input", columns=columns)
            column_configs = {
                pos: infer_column_type(sampled_values[name])
                for pos, name in position_to_name.items()
            }

            # Stage 6
            null_tokens = infer_null_tokens(conn, table_name="raw_input", columns=columns)

            # Stage 7
            row_count, column_counts = compute_column_counts(
                conn,
                table_name="raw_input",
                position_to_name=position_to_name,
                null_tokens=null_tokens,
            )

            # Stage 8
            sample_values_by_position = read_sample_values(
                conn,
                table_name="raw_input",
                position_to_name=position_to_name,
            )
    finally:
        if reading.prepared_ingestion.cleanup_path is not None:
            reading.prepared_ingestion.cleanup_path.unlink(missing_ok=True)

    return SuggestionOutput(
        source_format=reading.source_format,
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
        sample_rows=reading.sample_rows,
    )
