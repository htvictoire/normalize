"""SQL execution helpers for cell normalization table rewrite."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from normalize.stages.cell_normalization.sql_helpers import quote_identifier

_INDEX_AUDIT_COLUMNS = ("_row_index", "_global_row_index")


def execute_cell_rewrite(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    data_columns: Sequence[str],
    base_exprs: Sequence[str],
    raw_source_pairs: Sequence[str],
    issue_pairs: Sequence[str],
    row_error_terms: Sequence[str],
    available_columns: Sequence[str],
    full_raw_row: bool,
    emit_raw_row: bool,
    emit_parse_issues: bool,
) -> None:
    """Rewrite table with normalized values and audit payloads."""
    base_select_exprs: list[str] = list(base_exprs)
    has_row_indices = set(_INDEX_AUDIT_COLUMNS).issubset(set(available_columns))
    passthrough_audit = list(_INDEX_AUDIT_COLUMNS) if has_row_indices else []

    if emit_raw_row:
        base_select_exprs.append(
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
        base_select_exprs.append("ROW_NUMBER() OVER (ORDER BY rowid) AS _row_index")
        base_select_exprs.append("ROW_NUMBER() OVER (ORDER BY rowid) AS _global_row_index")
        passthrough_exprs = []
        passthrough_audit = list(_INDEX_AUDIT_COLUMNS)
    base_select_exprs.extend(passthrough_exprs)

    projected_columns = [
        quote_identifier(column) for column in list(data_columns) + passthrough_audit
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
