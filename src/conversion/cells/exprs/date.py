"""Date expression builder."""

from __future__ import annotations

from shared.constants import EXCEL_SERIAL_DATE_EPOCH_SQL
from shared.db.sql import quote_identifier, quote_string

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.naming import parse_date_alias


def build_date_exprs(
    column_name: str,
    nullish_predicate: str,
    raw_value: str,
    date_format: str,
    issue_label: str = "INVALID_DATE",
) -> ColumnExprs:
    """Build ColumnExprs for a date column."""
    date_alias = quote_identifier(parse_date_alias(column_name))
    if date_format == "EXCEL_SERIAL":
        date_expr = f"({EXCEL_SERIAL_DATE_EPOCH_SQL} + TRY_CAST({raw_value} AS INTEGER))"
    else:
        date_expr = (
            f"TRY_CAST(TRY_STRPTIME({raw_value}, {quote_string(date_format)}) AS DATE)"
        )
    normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {date_alias} END"
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {date_alias} IS NULL THEN '{issue_label}' "
        "ELSE NULL END"
    )
    return ColumnExprs(
        parse_cte_entries=((date_alias, date_expr),),
        normalized_expr=normalized,
        issue_expr=issue,
    )
