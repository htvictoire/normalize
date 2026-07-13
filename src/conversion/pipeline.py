"""Conversion pipeline — transform and quality computation.

Phase 1  rows          — count empty rows, build the RowPlan.
Phase 2  cells         — build per-column SQL expressions, build the CellPlan.
                         transform.py composes both plans into SQL and executes it.
Phase 3  quality_metrics — compute parse and completeness metrics from the normalized table.
"""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.column_index import resolve_column_config_by_canonical
from shared.db.sql import read_columns
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig

from conversion.cells import plan_cells
from conversion.models import TransformResult
from conversion.quality_metrics import compute_quality
from conversion.rows import plan_rows
from conversion.transform import compose_transform_sql


def run_conversion(
    conn: DuckDBPyConnection,
    confirmed_column_config: dict[str, ColumnConfig],
    operation_config: OperationConfig,
) -> TransformResult:
    """Run the conversion transform and quality computation against an open DuckDB connection."""
    raw_columns = read_columns(conn)
    if not raw_columns:
        raise ValueError("Conversion requires at least one data column")

    resolved_column_config = resolve_column_config_by_canonical(
        data_columns=raw_columns,
        column_config=confirmed_column_config,
    )

    row_plan = plan_rows(
        conn,
        columns=raw_columns,
        assign_indices=operation_config.assign_indices,
        drop_empty_rows=operation_config.drop_empty_rows,
    )

    cell_plan = plan_cells(
        column_config=resolved_column_config,
        null_tokens=operation_config.null_tokens,
        columns=raw_columns,
        full_raw_row=operation_config.full_raw_row,
    )

    conn.execute(compose_transform_sql(row_plan, cell_plan))

    return TransformResult(
        quality_output=compute_quality(conn, cell_plan.data_columns),
        cell_plan=cell_plan,
        row_plan=row_plan,
    )
