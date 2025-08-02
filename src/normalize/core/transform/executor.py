"""Execution of the combined row+cell transform."""

from __future__ import annotations

from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.transform.models import CellPlan, RowPlan
from normalize.core.transform.sql_builder import compose_transform_sql


def execute_combined_transform(
    conn: DuckDBPyConnection,
    row_plan: RowPlan,
    cell_plan: CellPlan,
    *,
    table_name: str = "raw_input",
) -> dict[str, object]:
    """Execute the composed transform SQL."""
    start = perf_counter()

    sql = compose_transform_sql(row_plan, cell_plan, table_name=table_name)
    conn.execute(sql)
    sql_seconds = perf_counter() - start

    rows_after = row_plan.rows_before - row_plan.rows_dropped

    return {
        "duration_seconds": perf_counter() - start,
        "sql_seconds": sql_seconds,
        "rows_before": row_plan.rows_before,
        "rows_after": rows_after,
        "rows_dropped": row_plan.rows_before - rows_after,
        "column_count": len(cell_plan.data_columns),
    }
