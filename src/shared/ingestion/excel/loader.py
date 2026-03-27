"""
Direct Excel loader.

Path:
Excel file -> openpyxl streaming (read_only=True) -> conn.executemany() -> destination table.
"""

from __future__ import annotations

import openpyxl
from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import quote_identifier
from shared.ingestion.contracts import HeaderMode


class DirectExcelIngestor:
    """
    Load Excel directly into DuckDB using openpyxl streaming.

    Performance notes:
    - uses read_only=True so openpyxl streams rows without loading the full workbook
    - keeps all columns as VARCHAR to match CSV ingestion behaviour
    - rows are inserted via executemany to avoid per-row round-trips
    """

    def run(
        self,
        conn: DuckDBPyConnection,
        source_url: str,
        sheet_name: str | None,
        header_mode: HeaderMode,
        header_row_index: int | None,
    ) -> list[str]:
        """
        Execute direct Excel ingestion.

        Returns:
        - ordered list of destination column names
        """

        wb = openpyxl.load_workbook(source_url, read_only=True, data_only=True)
        ws = wb[sheet_name] if sheet_name is not None else wb.worksheets[0]

        skip_count = (header_row_index - 1) if header_row_index is not None else 0
        column_names: list[str] = []
        rows: list[list[str]] = []

        for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
            if row_idx < skip_count:
                continue
            if header_mode is HeaderMode.PRESENT and row_idx == skip_count:
                column_names = [
                    str(cell).strip() if cell is not None else f"col_{i}"
                    for i, cell in enumerate(row)
                ]
                continue
            rows.append([str(cell) if cell is not None else "" for cell in row])

        wb.close()

        if not column_names:
            col_count = len(rows[0]) if rows else 0
            column_names = [f"col_{i}" for i in range(col_count)]

        if not column_names:
            conn.execute(f"CREATE OR REPLACE TABLE {RAW_INPUT_TABLE_NAME} (dummy VARCHAR)")
            return []

        quoted_cols = ", ".join(f"{quote_identifier(c)} VARCHAR" for c in column_names)
        conn.execute(f"CREATE OR REPLACE TABLE {RAW_INPUT_TABLE_NAME} ({quoted_cols})")

        if rows:
            placeholders = ", ".join(["?"] * len(column_names))
            conn.executemany(
                f"INSERT INTO {RAW_INPUT_TABLE_NAME} VALUES ({placeholders})",
                rows,
            )

        return column_names
