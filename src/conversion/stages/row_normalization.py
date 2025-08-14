"""Row normalization stage."""

from __future__ import annotations

from time import perf_counter

from duckdb import DuckDBPyConnection

from conversion.core.transform.models import RowPlan
from shared.db.sql import (
    quote_identifier,
    read_columns,
    validate_identifier,
)
from shared.stages.base import Stage


class RowNormalizationStage(Stage):
    """
    Normalize row-level structure for downstream deterministic processing.

    Responsibilities:
    - optionally drop fully empty rows (null/empty/whitespace across non-audit columns)
    - add `_row_index` starting at 1
    - add `_global_row_index` (same as `_row_index` in Phase 1)
    - publish row-count metrics

    Supports two execution modes:
    - `execute()` — standalone: runs the full row normalization as a separate pass
    - `plan()` — returns a RowPlan for use with the combined transform engine
    """

    def __init__(self, *, assign_indices: bool = True, drop_empty_rows: bool = True) -> None:
        super().__init__()
        self._assign_indices = assign_indices
        self._drop_empty_rows = drop_empty_rows

    def plan(self, conn: DuckDBPyConnection, table_name: str = "raw_input") -> RowPlan:
        """Build a RowPlan without executing any table mutations.

        Counts empty rows to enable the fast path (rowid+1 vs ROW_NUMBER).
        """
        validate_identifier(table_name)
        rows_before_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        if rows_before_row is None:
            raise RuntimeError("row count query returned no rows")
        rows_before = int(rows_before_row[0])

        filter_predicate: str | None = None
        rows_dropped = 0
        if self._drop_empty_rows:
            columns = read_columns(conn, table_name)
            data_columns = [
                col for col in columns if col not in {"_row_index", "_global_row_index"}
            ]
            filter_predicate = _build_non_empty_predicate(data_columns)
            non_empty_row = conn.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {filter_predicate}"
            ).fetchone()
            if non_empty_row is None:
                raise RuntimeError("non-empty row count query returned no rows")
            non_empty = int(non_empty_row[0])
            rows_dropped = rows_before - non_empty

        return RowPlan(
            filter_predicate=filter_predicate,
            assign_indices=self._assign_indices,
            rows_before=rows_before,
            rows_dropped=rows_dropped,
        )

    def execute(
        self, conn: DuckDBPyConnection, table_name: str = "raw_input"
    ) -> dict[str, int]:
        start_time = perf_counter()
        validate_identifier(table_name)

        rows_before_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        if rows_before_row is None:
            raise RuntimeError("row count query returned no rows")
        rows_before = int(rows_before_row[0])
        if self._drop_empty_rows:
            columns = read_columns(conn, table_name)
            data_columns = [
                col for col in columns if col not in {"_row_index", "_global_row_index"}
            ]
            non_empty_predicate = _build_non_empty_predicate(data_columns)

            if self._assign_indices:
                conn.execute(
                    f"""
                    CREATE OR REPLACE TABLE {table_name} AS
                    SELECT
                        *,
                        (ROW_NUMBER() OVER (ORDER BY rowid))::BIGINT AS _row_index,
                        (ROW_NUMBER() OVER (ORDER BY rowid))::BIGINT AS _global_row_index
                    FROM {table_name}
                    WHERE {non_empty_predicate}
                    ORDER BY rowid
                    """
                )
            else:
                conn.execute(
                    f"""
                    CREATE OR REPLACE TABLE {table_name} AS
                    SELECT *
                    FROM {table_name}
                    WHERE {non_empty_predicate}
                    ORDER BY rowid
                    """
                )
        elif self._assign_indices:
            conn.execute(
                f"""
                CREATE OR REPLACE TABLE {table_name} AS
                SELECT
                    *,
                    (ROW_NUMBER() OVER (ORDER BY rowid))::BIGINT AS _row_index,
                    (ROW_NUMBER() OVER (ORDER BY rowid))::BIGINT AS _global_row_index
                FROM {table_name}
                ORDER BY rowid
                """
            )

        rows_after_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        if rows_after_row is None:
            raise RuntimeError("row count query returned no rows")
        rows_after = int(rows_after_row[0])
        rows_dropped = rows_before - rows_after
        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "rows_dropped": rows_dropped,
            "assign_indices": self._assign_indices,
            "drop_empty_rows": self._drop_empty_rows,
        }
        return {
            "rows_before": rows_before,
            "rows_after": rows_after,
            "rows_dropped": rows_dropped,
        }


def _build_non_empty_predicate(columns: list[str]) -> str:
    if not columns:
        return "FALSE"
    checks = [f"LENGTH({_stripped_value_expr(col)}) > 0" for col in columns]
    return " OR ".join(checks)


def _stripped_value_expr(column_name: str) -> str:
    raw = f"COALESCE(CAST({quote_identifier(column_name)} AS VARCHAR), '')"
    # Remove common whitespace characters without regex:
    # space (32), tab (9), newline (10), carriage return (13).
    return (
        f"REPLACE(REPLACE(REPLACE(REPLACE({raw}, CHR(32), ''), "
        "CHR(9), ''), CHR(10), ''), CHR(13), '')"
    )
