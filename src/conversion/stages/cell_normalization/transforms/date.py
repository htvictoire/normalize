"""Date expression builder."""

from __future__ import annotations

from conversion.stages.cell_normalization.naming import parse_date_alias
from conversion.stages.cell_normalization.sql_helpers import quote_identifier, quote_string


def build_date_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    date_format: str,
) -> tuple[list[tuple[str, str]], str, str]:
    """Build (parse_cte_entries, normalized_expr, issue_expr) for a date column."""
    date_alias = quote_identifier(parse_date_alias(column_name))
    if date_format == "EXCEL_SERIAL":
        date_expr = f"(DATE '1899-12-30' + TRY_CAST({raw_value} AS INTEGER))"
    else:
        date_expr = (
            f"TRY_CAST(TRY_STRPTIME({raw_value}, {quote_string(date_format)}) AS DATE)"
        )
    normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {date_alias} END"
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {date_alias} IS NULL THEN 'INVALID_DATE' "
        "ELSE NULL END"
    )
    return ([(date_alias, date_expr)], normalized, issue)
