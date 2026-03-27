"""
Direct CSV loader.

Path:
CSV file -> DuckDB `read_csv` with explicit parse options -> destination table.
"""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import read_columns, validate_identifier
from shared.ingestion.contracts import HeaderMode
from shared.ingestion.csv.options import resolve_header_options


class DirectCsvIngestor:
    """
    Load CSV directly into DuckDB with explicit parse options.

    Performance notes:
    - uses `read_csv` (not `read_csv_auto`) to avoid extra auto-detection work
      because encoding, delimiter, and header behavior are already explicit
    - keeps all columns as `VARCHAR` in phase 1 (`all_varchar=true`) to avoid
      type inference cost at ingestion time
    """

    def run(
        self,
        conn: DuckDBPyConnection,
        source_url: str,
        *,
        encoding: str,
        delimiter: str,
        header_mode: HeaderMode,
        header_row_index: int | None,
    ) -> list[str]:
        """
        Execute direct CSV ingestion.

        Returns:
        - ordered list of destination column names
        """
        validate_identifier(RAW_INPUT_TABLE_NAME)
        header, skip = resolve_header_options(header_mode, header_row_index)
        conn.execute(
            f"CREATE OR REPLACE TABLE {RAW_INPUT_TABLE_NAME} AS "
            "SELECT * FROM read_csv("
            "?, header=?, skip=?, delim=?, encoding=?, all_varchar=true"
            ")",
            [source_url, header, skip, delimiter, encoding],
        )
        return read_columns(conn)
