"""
Direct JSON loader.

Path:
JSON file -> DuckDB read_json_auto() -> destination table.
"""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, read_columns, validate_identifier


class DirectJsonIngestor:
    """
    Load JSON directly into DuckDB using read_json_auto.

    All values are cast to VARCHAR to match CSV ingestion behaviour.
    """

    def run(
        self,
        conn: DuckDBPyConnection,
        source_url: str,
        *,
        table_name: str,
    ) -> list[str]:
        """
        Execute direct JSON ingestion.

        Returns:
        - ordered list of destination column names
        """
        validate_identifier(table_name)
        temp_table = "__json_input_raw"
        validate_identifier(temp_table)
        conn.execute(
            f"CREATE OR REPLACE TABLE {temp_table} AS "
            "SELECT * FROM read_json_auto(?)",
            [source_url],
        )
        columns = read_columns(conn, temp_table)
        if columns:
            cast_expr = ", ".join(
                f"CAST({quote_identifier(column)} AS VARCHAR) AS {quote_identifier(column)}"
                for column in columns
            )
            conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT {cast_expr} FROM {temp_table}"
            )
        else:
            conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM {temp_table}")
        conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
        return read_columns(conn, table_name)
