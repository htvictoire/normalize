"""Currency analysis helpers used by engine pipeline orchestration."""

from __future__ import annotations

from typing import Any

from normalize.core.domain import NormalizationIssue
from normalize.core.engine.issues import (
    build_mixed_currency_issue,
)
from normalize.stages.cell_normalization.currency_helpers import (
    build_currency_symbol_extract_expr,
)
from shared.db.sql import quote_identifier, quote_string
from shared.models.column import ColumnConfig, column_config_type


def collect_currency_analysis(
    conn: Any,
    *,
    column_config: dict[str, ColumnConfig],
    null_tokens: tuple[str, ...],
) -> dict[str, Any]:
    """Collect mixed-symbol warnings and pattern-consistency for currency columns."""
    currency_columns = [
        name for name, config in column_config.items() if column_config_type(config) == "currency"
    ]
    if not currency_columns:
        return {"pattern_consistency_ratio": 1.0, "issues": []}

    issues: list[NormalizationIssue] = []
    per_column_ratios: list[float] = []
    symbol_stats = read_currency_symbol_stats(
        conn,
        currency_columns=currency_columns,
        null_tokens=null_tokens,
    )

    for column_name in currency_columns:
        non_nullish_count = symbol_stats[column_name]["non_nullish_count"]
        symbol_counts = symbol_stats[column_name]["symbol_counts"]
        observed_symbols = [symbol for symbol, _ in symbol_counts]
        dominant_symbol: str | None = None
        dominant_symbol_count = 0
        if symbol_counts:
            dominant_symbol, dominant_symbol_count = max(
                symbol_counts,
                key=lambda item: (item[1], item[0]),
            )

        dominant_symbol_ratio = 1.0
        if len(observed_symbols) > 1 and non_nullish_count > 0:
            dominant_symbol_ratio = dominant_symbol_count / non_nullish_count
        per_column_ratios.append(dominant_symbol_ratio)

        if len(observed_symbols) > 1:
            issues.append(
                build_mixed_currency_issue(
                    column_name=column_name,
                    symbols=observed_symbols,
                    dominant_symbol=dominant_symbol,
                    dominant_symbol_ratio=dominant_symbol_ratio,
                )
            )

    pattern_consistency_ratio = (
        1.0 if not per_column_ratios else sum(per_column_ratios) / len(per_column_ratios)
    )
    return {
        "pattern_consistency_ratio": pattern_consistency_ratio,
        "issues": issues,
    }


def read_currency_symbol_stats(
    conn: Any,
    *,
    currency_columns: list[str],
    null_tokens: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Return per-column non-null counts and symbol frequency in one table scan."""
    result: dict[str, dict[str, Any]] = {
        col: {"non_nullish_count": 0, "symbol_counts": []} for col in currency_columns
    }
    if not currency_columns:
        return result

    casted_columns = ", ".join(
        f"CAST({quote_identifier(column_name)} AS VARCHAR) AS {quote_identifier(column_name)}"
        for column_name in currency_columns
    )
    unpivot_columns = ", ".join(quote_identifier(column_name) for column_name in currency_columns)
    nullish_predicate = build_nullish_predicate("raw_value", null_tokens)
    symbol_expr = build_currency_symbol_extract_expr("raw_value")

    count_rows = conn.execute(
        f"""
        WITH source AS (
            SELECT {casted_columns}
            FROM raw_input
        ), long_values AS (
            SELECT column_name, raw_value
            FROM source
            UNPIVOT INCLUDE NULLS (raw_value FOR column_name IN ({unpivot_columns}))
        ), filtered AS (
            SELECT
                column_name,
                raw_value,
                {symbol_expr} AS symbol
            FROM long_values
            WHERE NOT ({nullish_predicate})
        )
            SELECT column_name AS col_name, COUNT(*) AS non_nullish_count
            FROM filtered
            GROUP BY column_name
            """
    ).fetchall()
    for col_name, non_nullish_count in count_rows:
        result[str(col_name)]["non_nullish_count"] = int(non_nullish_count)

    rows = conn.execute(
        f"""
        WITH source AS (
            SELECT {casted_columns}
            FROM raw_input
        ), long_values AS (
            SELECT column_name, raw_value
            FROM source
            UNPIVOT INCLUDE NULLS (raw_value FOR column_name IN ({unpivot_columns}))
        ), filtered AS (
            SELECT
                column_name,
                raw_value,
                {symbol_expr} AS symbol
            FROM long_values
            WHERE NOT ({nullish_predicate})
        )
        SELECT column_name AS col_name, symbol, COUNT(*) AS symbol_count
        FROM filtered
        WHERE symbol IS NOT NULL
        GROUP BY column_name, symbol
        ORDER BY column_name, symbol_count DESC, symbol ASC
        """
    ).fetchall()

    for col_name, symbol, symbol_count in rows:
        result[str(col_name)]["symbol_counts"].append((str(symbol), int(symbol_count)))
    return result


def build_nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    """Build SQL predicate matching nullish values for one SQL value expression."""
    base_value = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized_tokens = sorted({token.strip().lower() for token in null_tokens if token.strip()})
    if not normalized_tokens:
        return f"{base_value} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base_value} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"
