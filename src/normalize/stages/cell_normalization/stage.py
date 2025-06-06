"""Cell normalization stage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.column_positions import build_position_to_name
from normalize.core.token_policy import TokenPolicy
from normalize.core.transform import CellPlan
from normalize.stages.base import Stage
from normalize.stages.cell_normalization.date_resolution import (
    resolve_date_formats_by_canonical,
)
from normalize.stages.cell_normalization.execution import execute_cell_rewrite
from normalize.stages.cell_normalization.fragments import (
    build_cell_expression_fragments,
)
from normalize.stages.cell_normalization.planning import build_cell_plan
from normalize.stages.cell_normalization.quality_precompute import (
    refresh_quality_profile_precompute,
)
from normalize.stages.cell_normalization.schema import (
    AUDIT_COLUMNS,
    validate_inferred_types,
)
from normalize.stages.cell_normalization.sql_helpers import (
    read_columns,
    validate_identifier,
)


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
        inferred_types: Mapping[str, str],
        *,
        table_name: str = "raw_input",
        null_tokens: Sequence[str] | None,
        boolean_true_tokens: Sequence[str] | None,
        boolean_false_tokens: Sequence[str] | None,
        decimal_separator: str = ".",
        thousand_separator: str = "",
        allow_leading_decimal_point: bool = False,
        date_formats: Mapping[str, str] | None = None,
        position_to_canonical: Mapping[str, str] | None = None,
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
        validate_inferred_types(inferred_types, data_columns)
        resolved_position_to_canonical = build_position_to_name(data_columns)
        resolved_date_formats_by_canonical = resolve_date_formats_by_canonical(
            date_formats=date_formats,
            position_to_canonical=resolved_position_to_canonical,
        )

        fragments = build_cell_expression_fragments(
            data_columns=data_columns,
            inferred_types=inferred_types,
            token_policy=token_policy,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            allow_leading_decimal_point=allow_leading_decimal_point,
            date_formats_by_canonical=resolved_date_formats_by_canonical,
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
        inferred_types: Mapping[str, str],
        *,
        table_name: str = "raw_input",
        null_tokens: Sequence[str] | None,
        boolean_true_tokens: Sequence[str] | None,
        boolean_false_tokens: Sequence[str] | None,
        decimal_separator: str = ".",
        thousand_separator: str = "",
        allow_leading_decimal_point: bool = False,
        date_formats: Mapping[str, str] | None = None,
        position_to_canonical: Mapping[str, str] | None = None,
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
        validate_inferred_types(inferred_types, data_columns)
        resolved_position_to_canonical = build_position_to_name(data_columns)
        resolved_date_formats_by_canonical = resolve_date_formats_by_canonical(
            date_formats=date_formats,
            position_to_canonical=resolved_position_to_canonical,
        )

        fragments = build_cell_expression_fragments(
            data_columns=data_columns,
            inferred_types=inferred_types,
            token_policy=token_policy,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            allow_leading_decimal_point=allow_leading_decimal_point,
            date_formats_by_canonical=resolved_date_formats_by_canonical,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )

        execute_cell_rewrite(
            conn,
            table_name=table_name,
            data_columns=data_columns,
            base_exprs=fragments.base_exprs,
            raw_source_pairs=fragments.raw_source_pairs,
            issue_pairs=fragments.issue_pairs,
            row_error_terms=fragments.row_error_terms,
            available_columns=columns,
            full_raw_row=full_raw_row,
            emit_raw_row=emit_raw_row,
            emit_parse_issues=emit_parse_issues,
        )
        refresh_quality_profile_precompute(conn, table_name=table_name, data_columns=data_columns)

        row_count = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "rows_processed": row_count,
            "column_count": len(data_columns),
            "full_raw_row": full_raw_row,
            "emit_raw_row": emit_raw_row,
            "emit_parse_issues": emit_parse_issues,
        }
        return {"rows_processed": row_count, "column_count": len(data_columns)}
