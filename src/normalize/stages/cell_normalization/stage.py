"""Cell normalization stage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.token_policy import TokenPolicy
from normalize.core.transform import CellPlan
from normalize.stages.base import Stage
from normalize.stages.cell_normalization.schema import (
    AUDIT_COLUMNS,
    validate_inferred_types,
)
from normalize.stages.cell_normalization.sql_helpers import (
    quote_identifier,
    read_columns,
    validate_identifier,
)
from normalize.stages.cell_normalization.transforms import (
    build_column_exprs,
    build_nullish_predicate,
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

        base_exprs: list[str] = []
        raw_source_pairs: list[str] = []
        issue_pairs: list[str] = []
        row_error_terms: list[str] = []

        for column_name in data_columns:
            inferred_type = inferred_types[column_name]
            nullish_pred = build_nullish_predicate(column_name, token_policy.null_tokens)
            normalized_expr, issue_expr = build_column_exprs(
                column_name,
                inferred_type,
                nullish_pred,
                true_tokens=token_policy.boolean_true_tokens,
                false_tokens=token_policy.boolean_false_tokens,
            )
            issue_alias = _issue_alias(column_name)
            base_exprs.append(f"{normalized_expr} AS {quote_identifier(column_name)}")
            base_exprs.append(f"{issue_expr} AS {quote_identifier(issue_alias)}")
            row_error_terms.append(
                f"CASE WHEN {quote_identifier(issue_alias)} IS NULL THEN 0 ELSE 1 END"
            )
            if emit_raw_row:
                raw_source_pairs.append(
                    f"{quote_identifier(column_name)} := "
                    f"CAST({quote_identifier(column_name)} AS VARCHAR)"
                )
            if emit_parse_issues:
                issue_pairs.append(
                    f"{quote_identifier(column_name)} := {quote_identifier(issue_alias)}"
                )

        row_error_expr = "0" if not row_error_terms else " + ".join(row_error_terms)

        if emit_raw_row:
            full_raw_row_expr = "__raw_json"
            if full_raw_row:
                raw_row_expr = full_raw_row_expr
            else:
                raw_row_expr = (
                    f"CASE WHEN _parse_error_count = 0 THEN NULL ELSE {full_raw_row_expr} END"
                )
        else:
            raw_row_expr = "NULL::VARCHAR"

        if emit_parse_issues:
            parse_issues_expr = (
                "CASE WHEN _parse_error_count = 0 THEN NULL "
                f"ELSE TO_JSON(STRUCT_PACK({', '.join(issue_pairs)})) END"
            )
        else:
            parse_issues_expr = "NULL::VARCHAR"

        return CellPlan(
            data_columns=tuple(data_columns),
            column_select_exprs=tuple(base_exprs),
            raw_source_pairs=tuple(raw_source_pairs),
            issue_pairs=tuple(issue_pairs),
            row_error_expr=row_error_expr,
            raw_row_expr=raw_row_expr,
            parse_issues_expr=parse_issues_expr,
            emit_raw_row=emit_raw_row,
            full_raw_row=full_raw_row,
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

        base_exprs: list[str] = []
        raw_source_pairs: list[str] = []
        issue_pairs: list[str] = []
        row_error_terms: list[str] = []
        has_row_indices = {"_row_index", "_global_row_index"}.issubset(set(columns))
        passthrough_audit = ["_row_index", "_global_row_index"] if has_row_indices else []

        for column_name in data_columns:
            inferred_type = inferred_types[column_name]
            nullish_pred = build_nullish_predicate(column_name, token_policy.null_tokens)
            normalized_expr, issue_expr = build_column_exprs(
                column_name,
                inferred_type,
                nullish_pred,
                true_tokens=token_policy.boolean_true_tokens,
                false_tokens=token_policy.boolean_false_tokens,
            )
            issue_alias = _issue_alias(column_name)
            base_exprs.append(f"{normalized_expr} AS {quote_identifier(column_name)}")
            if emit_raw_row:
                raw_source_pairs.append(
                    f"{quote_identifier(column_name)} := "
                    f"CAST({quote_identifier(column_name)} AS VARCHAR)"
                )
            base_exprs.append(f"{issue_expr} AS {quote_identifier(issue_alias)}")
            row_error_terms.append(
                f"CASE WHEN {quote_identifier(issue_alias)} IS NULL THEN 0 ELSE 1 END"
            )
            if emit_parse_issues:
                issue_pairs.append(
                    f"{quote_identifier(column_name)} := {quote_identifier(issue_alias)}"
                )

        if emit_raw_row:
            base_exprs.append(
                f"TO_JSON(STRUCT_PACK({', '.join(raw_source_pairs)})) AS __raw_row_json"
            )

        if has_row_indices:
            passthrough_exprs = [
                f"{quote_identifier(column)} AS {quote_identifier(column)}"
                for column in passthrough_audit
            ]
        else:
            # High-throughput path: when step 3 runs without index materialization,
            # assign deterministic row indices here in the same rewrite pass.
            base_exprs.append("ROW_NUMBER() OVER (ORDER BY rowid) AS _row_index")
            base_exprs.append("ROW_NUMBER() OVER (ORDER BY rowid) AS _global_row_index")
            passthrough_exprs = []
            passthrough_audit = ["_row_index", "_global_row_index"]
        base_select_exprs = base_exprs + passthrough_exprs
        projected_columns = [
            quote_identifier(column) for column in data_columns + passthrough_audit
        ]
        row_error_expr = "0" if not row_error_terms else " + ".join(row_error_terms)
        if emit_raw_row:
            full_raw_row_expr = "__raw_row_json"
            if full_raw_row:
                raw_row_expr = full_raw_row_expr
            else:
                raw_row_expr = (
                    f"CASE WHEN _parse_error_count = 0 THEN NULL ELSE {full_raw_row_expr} END"
                )
        else:
            raw_row_expr = "NULL::VARCHAR"
        if emit_parse_issues:
            parse_issues_expr = (
                "CASE WHEN _parse_error_count = 0 THEN NULL "
                f"ELSE TO_JSON(STRUCT_PACK({', '.join(issue_pairs)})) END"
            )
        else:
            parse_issues_expr = "NULL::VARCHAR"

        conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            WITH stage_base AS (
                SELECT
                    {", ".join(base_select_exprs)}
                FROM {table_name}
            ),
            stage_enriched AS (
                SELECT
                    *,
                    ({row_error_expr})::INTEGER AS _parse_error_count
                FROM stage_base
            )
            SELECT
                {", ".join(projected_columns)},
                _parse_error_count,
                {raw_row_expr} AS _raw_row,
                {parse_issues_expr} AS _parse_issues
            FROM stage_enriched
            """
        )
        _refresh_quality_profile_precompute(conn, table_name=table_name, data_columns=data_columns)

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


def _issue_alias(column_name: str) -> str:
    return f"__issue__{column_name}"


def _refresh_quality_profile_precompute(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    data_columns: Sequence[str],
) -> None:
    """
    Materialize lightweight per-column counters for quality stage.

    Stored table:
    - `_quality_profile_raw_input`
      - `column_name`
      - `row_count`
      - `nullish_count`
      - `non_null_count`
    """
    profile_table = "_quality_profile_raw_input"
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {profile_table} (
            column_name VARCHAR,
            row_count BIGINT,
            nullish_count BIGINT,
            non_null_count BIGINT
        )
        """
    )
    if not data_columns:
        return

    aggregate_exprs: list[str] = ["COUNT(*) AS row_count"]
    for column_name in data_columns:
        quoted = quote_identifier(column_name)
        aggregate_exprs.append(
            f"SUM(CASE WHEN {quoted} IS NULL THEN 1 ELSE 0 END) AS {column_name}__nullish_count"
        )
        aggregate_exprs.append(f"COUNT({quoted}) AS {column_name}__non_null_count")

    row = conn.execute(f"SELECT {', '.join(aggregate_exprs)} FROM {table_name}").fetchone()
    if row is None:
        raise RuntimeError("quality precompute query returned no rows")

    row_count = int(row[0])
    rows_for_insert: list[tuple[str, int, int, int]] = []
    offset = 1
    for column_name in data_columns:
        nullish_count = int(row[offset])
        non_null_count = int(row[offset + 1])
        offset += 2
        rows_for_insert.append((column_name, row_count, nullish_count, non_null_count))

    conn.executemany(
        f"""
        INSERT INTO {profile_table}
            (column_name, row_count, nullish_count, non_null_count)
        VALUES (?, ?, ?, ?)
        """,
        rows_for_insert,
    )
