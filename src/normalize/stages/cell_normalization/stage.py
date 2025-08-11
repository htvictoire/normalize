"""Cell normalization stage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.token_policy import TokenPolicy
from normalize.core.transform.models import CellPlan
from normalize.stages.cell_normalization.execution import execute_cell_rewrite
from normalize.stages.cell_normalization.fragments import (
    build_cell_expression_fragments,
)
from normalize.stages.cell_normalization.planning import build_cell_plan
from normalize.stages.cell_normalization.schema import AUDIT_COLUMNS
from normalize.stages.cell_normalization.sql_helpers import (
    read_columns,
    validate_identifier,
)
from shared.models.column import ColumnConfig
from shared.stages.base import Stage


class CellNormalizationStage(Stage):
    """
    Normalize cell values using inferred types and null-token policy.

    Stage effects:
    - replace null tokens with SQL NULL
    - cast columns according to inferred types
    - optionally add `_raw_row` JSON payload with original row values
    - optionally add `_parse_issues` JSON payload with per-column issue codes

    Token policy is explicit and mandatory:
    - `null_tokens`
    - `boolean_true_tokens`
    - `boolean_false_tokens`

    Boolean normalization uses token mapping only; no regex or implicit values.

    Performance note:
    - By default `_raw_row` is materialized only for rows with parse issues
      (`full_raw_row=False`) to reduce large-dataset JSON cost.
    - `_raw_row` and `_parse_issues` can be disabled for throughput-focused
      runs while preserving `_parse_error_count`.
    """

    def plan(
        self,
        conn: DuckDBPyConnection,
        *,
        column_config: Mapping[str, ColumnConfig],
        table_name: str = "raw_input",
        null_tokens: Sequence[str] | None,
        boolean_true_tokens: Sequence[str] | None,
        boolean_false_tokens: Sequence[str] | None,
        full_raw_row: bool = False,
        emit_raw_row: bool = True,
        emit_parse_issues: bool = True,
    ) -> CellPlan:
        """Build a CellPlan with SQL fragments, without executing anything."""
        validate_identifier(table_name)
        token_policy = TokenPolicy.from_user_inputs(
            null_tokens=null_tokens,
            boolean_true_tokens=boolean_true_tokens,
            boolean_false_tokens=boolean_false_tokens,
        )

        columns = read_columns(conn, table_name)
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
        *,
        column_config: Mapping[str, ColumnConfig],
        table_name: str = "raw_input",
        null_tokens: Sequence[str] | None,
        boolean_true_tokens: Sequence[str] | None,
        boolean_false_tokens: Sequence[str] | None,
        full_raw_row: bool = False,
        emit_raw_row: bool = True,
        emit_parse_issues: bool = True,
    ) -> dict[str, int]:
        start_time = perf_counter()
        validate_identifier(table_name)
        token_policy = TokenPolicy.from_user_inputs(
            null_tokens=null_tokens,
            boolean_true_tokens=boolean_true_tokens,
            boolean_false_tokens=boolean_false_tokens,
        )

        columns = read_columns(conn, table_name)
        data_columns = [column for column in columns if column not in AUDIT_COLUMNS]

        fragments = build_cell_expression_fragments(
            data_columns=data_columns,
            column_config=column_config,
            token_policy=token_policy,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )

        execute_cell_rewrite(
            conn,
            table_name=table_name,
            data_columns=data_columns,
            parse_cte_entries=fragments.parse_cte_entries,
            base_exprs=fragments.base_exprs,
            raw_source_pairs=fragments.raw_source_pairs,
            issue_pairs=fragments.issue_pairs,
            row_error_terms=fragments.row_error_terms,
            available_columns=columns,
            full_raw_row=full_raw_row,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )

        row_count_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        if row_count_row is None:
            raise RuntimeError("row count query returned no rows")
        row_count = int(row_count_row[0])
        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "rows_processed": row_count,
            "column_count": len(data_columns),
            "full_raw_row": full_raw_row,
            "emit_raw_row": emit_raw_row,
            "emit_parse_issues": emit_parse_issues,
        }
        return {"rows_processed": row_count, "column_count": len(data_columns)}
