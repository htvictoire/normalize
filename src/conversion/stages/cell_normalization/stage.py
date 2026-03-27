"""Cell normalization stage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, read_columns
from shared.models.column import ColumnConfig
from shared.stage import Stage

from conversion.core.token_policy import TokenPolicy
from conversion.core.transform.models import CellPlan, RowPlan
from conversion.core.transform.sql_builder import compose_transform_sql
from conversion.stages.cell_normalization.fragments import (
    build_cell_expression_fragments,
)
from conversion.stages.cell_normalization.planning import build_cell_plan
from conversion.stages.cell_normalization.schema import AUDIT_COLUMNS


class CellNormalizationStage(Stage):
    """
    Rewrite the working table with typed, normalized values.

    - Null tokens and empty/whitespace cells are replaced with SQL NULL.
    - Each column is cast to its declared type.
    - Boolean tokens are read from each column's BooleanColumnConfig.
    - `_raw_row` is written only for rows with parse issues unless full_raw_row is set.
    - `_raw_row` and `_parse_issues` can be disabled independently.
    """

    def plan(
        self,
        column_config: Mapping[str, ColumnConfig],
        null_tokens: Sequence[str],
        columns: list[str],
        full_raw_row: bool = False,
        emit_raw_row: bool = True,
        emit_parse_issues: bool = True,
    ) -> CellPlan:
        """Build a CellPlan with SQL fragments, without executing anything.

        `columns` is the full ordered column list as read after header canonicalization.
        """
        token_policy = TokenPolicy.from_user_inputs(null_tokens)

        data_columns = [column for column in columns if column not in AUDIT_COLUMNS]

        fragments = build_cell_expression_fragments(
            data_columns=data_columns,
            column_config=column_config,
            token_policy=token_policy,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )
        return build_cell_plan(
            data_columns=tuple(data_columns),
            fragments=fragments,
            full_raw_row=full_raw_row,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )

    def execute(
        self,
        conn: DuckDBPyConnection,
        column_config: Mapping[str, ColumnConfig],
        null_tokens: Sequence[str],
        full_raw_row: bool = False,
        emit_raw_row: bool = True,
        emit_parse_issues: bool = True,
    ) -> dict[str, int]:
        start_time = perf_counter()
        columns = read_columns(conn)
        cell_plan = self.plan(
            column_config=column_config,
            null_tokens=null_tokens,
            columns=columns,
            full_raw_row=full_raw_row,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )
        row_plan = RowPlan(
            filter_predicate=None, assign_indices=False, rows_before=0, rows_dropped=0
        )
        conn.execute(compose_transform_sql(row_plan, cell_plan))

        row_count = execute_scalar(conn, f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME}")
        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "rows_processed": row_count,
            "column_count": len(cell_plan.data_columns),
            "full_raw_row": full_raw_row,
            "emit_raw_row": emit_raw_row,
            "emit_parse_issues": emit_parse_issues,
        }
        return {"rows_processed": row_count, "column_count": len(cell_plan.data_columns)}
