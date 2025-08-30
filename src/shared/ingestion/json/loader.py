"""
Direct JSON loader.

Path:
JSON file -> DuckDB read_json_auto() -> destination table.
"""

from __future__ import annotations

from pathlib import Path

from duckdb import DuckDBPyConnection

from shared.db.sql import read_columns, validate_identifier


class DirectJsonIngestor:
    """
    Load JSON directly into DuckDB using read_json_auto.

    All values are cast to VARCHAR to match CSV ingestion behaviour.
    """

    def run(
        self,
        conn: DuckDBPyConnection,
        json_path: Path,
        *,
        table_name: str,
    ) -> list[str]:
        """
        Execute direct JSON ingestion.

        Returns:
        - ordered list of destination column names
        """
        validate_identifier(table_name)
        conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS "
            "SELECT * FROM read_json_auto(?, all_varchar=true)",
            [str(json_path)],
        )
        return read_columns(conn, table_name)
