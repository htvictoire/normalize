"""
Suggestion pipeline — infers provisional settings for one source file.

Phase 1  Read source: infer format settings and collect raw sample rows in one
         pass. CSV and JSON use a single byte probe; Excel opens the workbook once.

Phase 2  Ingest into an in-memory DuckDB table using the inferred format.

Phase 3  Derive ordered column labels and position keys.

Phase 4  Infer a ColumnConfig (type, separators, date format, …) per column
         from a random sample of up to 256 non-null values.

Phase 5  Infer null tokens from recurring empty-looking values across all columns.

Phase 6  Compute null / non-null counts per column using the inferred null tokens.

Phase 7  Collect per-column sample values for display.
"""

from __future__ import annotations

from shared.db.duckdb import DuckDBManager
from shared.db.sql import compute_column_counts
from shared.ingestion import IngestionRequest, run_ingestion
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestedColumn, SuggestionOutput
from shared.utils.column import build_position_to_name
from suggestion.column_config.inference import infer_column_type
from suggestion.column_config.sampler import sample_column_values
from suggestion.column_display import read_sample_values
from suggestion.constants import SUGGESTION_TABLE_NAME
from suggestion.null_tokens import infer_null_tokens
from suggestion.source.read import read_source


def run_suggestion(source: SourceRef) -> SuggestionOutput:
    """Run suggestion pipeline for one source file."""
    # Phase 1
    reading = read_source(source)
    try:
        with DuckDBManager() as conn:
            # Phase 2
            ingestion = run_ingestion(
                IngestionRequest(
                    conn=conn,
                    source_url=reading.ingestion_source_url,
                    source_type=reading.ingestion_source_type,
                    source_format=reading.source_format,
                    table_name=SUGGESTION_TABLE_NAME,
                )
            )

            # Phase 3
            position_to_name = build_position_to_name(ingestion.column_names)

            # Phase 4
            sampled_values = sample_column_values(
                conn, table_name=SUGGESTION_TABLE_NAME, columns=ingestion.column_names
            )
            column_configs = {
                pos: infer_column_type(sampled_values[name])
                for pos, name in position_to_name.items()
            }

            # Phase 5
            null_tokens = infer_null_tokens(
                conn, table_name=SUGGESTION_TABLE_NAME, columns=ingestion.column_names
            )

            # Phase 6
            row_count, column_counts = compute_column_counts(
                conn,
                table_name=SUGGESTION_TABLE_NAME,
                position_to_name=position_to_name,
                null_tokens=null_tokens,
            )

            # Phase 7
            sample_values_by_position = read_sample_values(
                conn,
                table_name=SUGGESTION_TABLE_NAME,
                position_to_name=position_to_name,
            )
    finally:
        if reading.cleanup_path is not None:
            reading.cleanup_path.unlink(missing_ok=True)

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
