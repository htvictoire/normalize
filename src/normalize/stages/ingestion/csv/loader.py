"""
Direct CSV loader.

Path:
CSV file -> DuckDB `read_csv` with explicit parse options -> destination table.
"""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from normalize.core.sql_helpers import read_columns, validate_identifier
from normalize.stages.ingestion.contracts import HeaderMode
from normalize.stages.ingestion.csv.options import resolve_header_options


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
        csv_path: Path,
        *,
        table_name: str,
        encoding: str,
        delimiter: str,
        header_mode: HeaderMode,
        header_row_index: int | None,
    ) -> tuple[int, list[str]]:
        """
        Execute direct CSV ingestion.

        Returns:
        - row count loaded into destination table
        - ordered list of destination column names
        """
        validate_identifier(table_name)
        header, skip = resolve_header_options(header_mode, header_row_index)
        conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS "
            "SELECT * FROM read_csv("
            "?, header=?, skip=?, delim=?, encoding=?, all_varchar=true"
            ")",
            [str(csv_path), header, skip, delimiter, encoding],
        )
        row_count = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        column_names = read_columns(conn, table_name)
        return (row_count, column_names)
