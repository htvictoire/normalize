"""Monetary symbol profiling stats for currency and accounting types.

Currency and accounting metrics are computed via one shared grouped query across
all symbol-bearing columns. We keep that mixed query because splitting the work
into separate currency/accounting batches would add another grouped table scan
without changing the resulting metrics. The returned metric types are still
separate so the Python type model reflects the real per-column shape.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier, quote_string
from shared.models.column import AccountingColumnConfig, CurrencyColumnConfig
from shared.models.profiling import (
    AccountingColumnProfile,
    ColumnCounts,
    CurrencyColumnProfile,
)
from shared.parsing.currency import (
    CURRENCY_TOKEN_PATTERN_LOWER,
    build_currency_symbol_extract_expr,
)
from shared.parsing.markers import has_marker, strip_marker

from profiling.column_stats.common import DecimalParseStats


@dataclass(frozen=True)
class SymbolColumnEntry:
    column_name: str
    config: CurrencyColumnConfig | AccountingColumnConfig
    counts: ColumnCounts
    value_expr: str


@dataclass(frozen=True)
class BaseSymbolColumnMetrics:
    symbol_distribution: dict[str, int]


@dataclass(frozen=True)
class CurrencyColumnMetrics(BaseSymbolColumnMetrics):
    symbol_position_distribution: dict[str, int]


@dataclass(frozen=True)
class AccountingColumnMetrics(BaseSymbolColumnMetrics):
    sign_notation_distribution: dict[str, int]
    negative_marker_distribution: dict[str, int]
    positive_marker_distribution: dict[str, int]


SymbolColumnMetrics = CurrencyColumnMetrics | AccountingColumnMetrics


@dataclass(frozen=True)
class SymbolCoverageStats:
    non_nullish_count: int
    symbol_distribution: dict[str, int]
    symbol_detected_count: int
    symbol_detected_ratio: float
    missing_symbol_count: int
    missing_symbol_ratio: float
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool


class SymbolBaseProfileFields(TypedDict):
    symbol_distribution: dict[str, int]
    symbol_detected_count: int
    symbol_detected_ratio: float
    missing_symbol_count: int
    missing_symbol_ratio: float
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool
    parse_match_count: int
    parse_match_ratio: float
    comma_decimal_count: int
    dot_decimal_count: int
    mixed_number_format_detected: bool
    max_scale: int
    max_integer_digits: int


def _ordered_count_dict(counts: Mapping[str, int]) -> dict[str, int]:
    return {key: counts[key] for key in sorted(counts, key=lambda key: (-counts[key], key))}


def _dominant_count(distribution: dict[str, int]) -> tuple[str | None, int]:
    dominant = next(iter(distribution), None)
    return dominant, 0 if dominant is None else distribution[dominant]


def _token_form(symbol: str) -> str:
    has_alpha = any(char.isalpha() for char in symbol)
    has_non_alpha = any(not char.isalpha() for char in symbol)
    if has_alpha and not has_non_alpha:
        return "code"
    if has_alpha and has_non_alpha:
        return "composite"
    return "symbol"


def _strip_structural_sign_for_symbol(value_expr: str) -> str:
    """Return SQL that removes parentheses and leading/trailing sign chars."""
    trimmed = f"TRIM({value_expr})"
    inner_paren = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
    paren_stripped = (
        "CASE "
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) THEN {inner_paren} "
        f"ELSE {trimmed} END"
    )
    leading_stripped = f"TRIM(REGEXP_REPLACE({paren_stripped}, {quote_string(r'^[+-]\s*')}, ''))"
    return f"TRIM(REGEXP_REPLACE({leading_stripped}, {quote_string(r'\s*[+-]$')}, ''))"


def _build_symbol_source_expr(
    value_expr: str,
    config: CurrencyColumnConfig | AccountingColumnConfig,
) -> str:
    """Return SQL normalized for symbol extraction.

    Currency values strip only structural signs. Accounting values also strip any
    configured positive/negative markers before extracting the currency token.
    """
    trimmed = f"TRIM({value_expr})"
    structural = _strip_structural_sign_for_symbol(trimmed)
    if isinstance(config, CurrencyColumnConfig):
        return structural

    markers = tuple(dict.fromkeys((*config.negative_markers, *config.positive_markers)))
    cases: list[str] = []
    for marker in markers:
        stripped = _strip_structural_sign_for_symbol(strip_marker(trimmed, marker))
        cases.append(
            f"WHEN {has_marker(trimmed, marker)} "
            f"THEN {stripped}"
        )
    if not cases:
        return structural
    return "CASE " + " ".join(cases) + f" ELSE {structural} END"


def _build_symbol_extract_expr(
    value_expr: str,
    config: CurrencyColumnConfig | AccountingColumnConfig,
) -> str:
    """Return SQL that extracts the currency token from a normalized monetary value."""
    return build_currency_symbol_extract_expr(_build_symbol_source_expr(value_expr, config))


def _build_symbol_position_expr(source_expr: str) -> str:
    """Return SQL that classifies the normalized currency token as prefix or suffix."""
    trimmed = f"TRIM({source_expr})"
    lowered = f"LOWER({trimmed})"
    token_pattern = CURRENCY_TOKEN_PATTERN_LOWER
    prefix_match = (
        f"REGEXP_FULL_MATCH({lowered}, "
        f"{quote_string(rf'^{token_pattern}\s*.+$')})"
    )
    suffix_match = (
        f"REGEXP_FULL_MATCH({lowered}, "
        f"{quote_string(rf'^.+\s*{token_pattern}$')})"
    )
    return (
        "CASE "
        f"WHEN NULLIF({trimmed}, '') IS NULL THEN NULL "
        f"WHEN {prefix_match} THEN 'prefix' "
        f"WHEN {suffix_match} THEN 'suffix' "
        "ELSE NULL END"
    )


def _build_marker_expr(value_expr: str, markers: tuple[str, ...]) -> str:
    """Return SQL that captures the matched marker token for distribution counts."""
    trimmed = f"TRIM({value_expr})"
    cases: list[str] = []
    for marker in markers:
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN {quote_string(marker)}")
    if not cases:
        return "NULL"
    return "CASE " + " ".join(cases) + " ELSE NULL END"


def _build_sign_notation_expr(value_expr: str, config: AccountingColumnConfig) -> str:
    """Return SQL that classifies accounting sign notation into stable buckets."""
    trimmed = f"TRIM({value_expr})"
    cases: list[str] = []
    for marker in config.negative_markers:
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN 'negative_marker'")
    for marker in config.positive_markers:
        cases.append(f"WHEN {has_marker(trimmed, marker)} THEN 'positive_marker'")
    cases.append(
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) THEN 'parentheses'"
    )
    cases.append(
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^[+-]\s*.+$')}) THEN 'leading_sign'"
    )
    cases.append(
        f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^.+\s*[+-]$')}) THEN 'trailing_sign'"
    )
    return "CASE " + " ".join(cases) + " ELSE 'unsigned' END"


def compute_symbol_metrics_batch(
    conn: DuckDBPyConnection,
    batch: list[SymbolColumnEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, SymbolColumnMetrics]:
    """Return batched per-column monetary metric distributions.

    The query first aliases each symbol-bearing column once in ``base``. It then
    projects tagged ``(column_name, metric_name, metric_value)`` rows via
    ``LATERAL (VALUES ...)`` so all per-column symbol/sign distributions can be
    aggregated in one grouped query instead of one ``GROUP BY`` per column.

    We intentionally keep currency and accounting columns in this one query even
    though they produce different metric dataclasses. Splitting them into two
    batches would make the type shapes cleaner inside SQL assembly, but it would
    also turn one grouped metrics scan into two.
    """
    if not batch:
        return {}

    base_exprs: list[str] = []
    value_rows: list[str] = []
    for idx, entry in enumerate(batch):
        alias = quote_identifier(f"__sym{idx}")
        base_exprs.append(f"{quote_identifier(entry.column_name)} AS {alias}")
        nullish = nullish_predicate(alias, null_tokens)
        source_expr = _build_symbol_source_expr(alias, entry.config)
        symbol_expr = _build_symbol_extract_expr(alias, entry.config)
        value_rows.append(
            f"({quote_string(entry.column_name)}, 'symbol', "
            f"CASE WHEN NOT ({nullish}) THEN {symbol_expr} ELSE NULL END)"
        )
        if isinstance(entry.config, CurrencyColumnConfig):
            position_expr = _build_symbol_position_expr(source_expr)
            value_rows.append(
                f"({quote_string(entry.column_name)}, 'symbol_position', "
                f"CASE WHEN NOT ({nullish}) THEN {position_expr} ELSE NULL END)"
            )
        else:
            value_rows.append(
                f"({quote_string(entry.column_name)}, 'sign_notation', "
                f"CASE WHEN NOT ({nullish}) THEN {_build_sign_notation_expr(alias, entry.config)} "
                "ELSE NULL END)"
            )
            value_rows.append(
                f"({quote_string(entry.column_name)}, 'negative_marker', "
                f"CASE WHEN NOT ({nullish}) "
                f"THEN {_build_marker_expr(alias, entry.config.negative_markers)} "
                "ELSE NULL END)"
            )
            value_rows.append(
                f"({quote_string(entry.column_name)}, 'positive_marker', "
                f"CASE WHEN NOT ({nullish}) "
                f"THEN {_build_marker_expr(alias, entry.config.positive_markers)} "
                "ELSE NULL END)"
            )

    rows = conn.execute(
        "WITH base AS ("
        f"SELECT {', '.join(base_exprs)} FROM {RAW_INPUT_TABLE_NAME}"
        ") "
        "SELECT column_name, metric_name, metric_value, COUNT(*) AS c "
        "FROM base, "
        # Emit tagged metric rows from one base scan so all symbol-bearing columns
        # feed a single grouped aggregation instead of one GROUP BY per column.
        "LATERAL (VALUES "
        f"{', '.join(value_rows)}"
        ") AS v(column_name, metric_name, metric_value) "
        "WHERE metric_value IS NOT NULL "
        "GROUP BY column_name, metric_name, metric_value "
        "ORDER BY column_name ASC, metric_name ASC, c DESC, metric_value ASC"
    ).fetchall()

    buckets: dict[str, dict[str, dict[str, int]]] = {
        entry.column_name: {
            "symbol": {},
            "symbol_position": {},
            "sign_notation": {},
            "negative_marker": {},
            "positive_marker": {},
        }
        for entry in batch
    }
    for column_name, metric_name, metric_value, count in rows:
        buckets[str(column_name)][str(metric_name)][str(metric_value)] = int(count)

    result: dict[str, SymbolColumnMetrics] = {}
    for entry in batch:
        distributions = buckets[entry.column_name]
        symbol_distribution = _ordered_count_dict(distributions["symbol"])
        if isinstance(entry.config, CurrencyColumnConfig):
            result[entry.column_name] = CurrencyColumnMetrics(
                symbol_distribution=symbol_distribution,
                symbol_position_distribution=_ordered_count_dict(
                    distributions["symbol_position"]
                ),
            )
        else:
            result[entry.column_name] = AccountingColumnMetrics(
                symbol_distribution=symbol_distribution,
                sign_notation_distribution=_ordered_count_dict(
                    distributions["sign_notation"]
                ),
                negative_marker_distribution=_ordered_count_dict(
                    distributions["negative_marker"]
                ),
                positive_marker_distribution=_ordered_count_dict(
                    distributions["positive_marker"]
                ),
            )
    return result


def _build_token_form_distribution(symbol_distribution: Mapping[str, int]) -> dict[str, int]:
    counts_by_form: dict[str, int] = defaultdict(int)
    for symbol, count in symbol_distribution.items():
        counts_by_form[_token_form(symbol)] += count
    return _ordered_count_dict(counts_by_form)


def _build_symbol_coverage_stats(
    counts: ColumnCounts,
    metrics: BaseSymbolColumnMetrics,
) -> SymbolCoverageStats:
    symbol_distribution = metrics.symbol_distribution
    symbol_detected_count = sum(symbol_distribution.values())
    non_nullish = counts.non_nullish_count
    missing_symbol_count = non_nullish - symbol_detected_count
    dominant_symbol, dominant_count = _dominant_count(symbol_distribution)
    return SymbolCoverageStats(
        non_nullish_count=non_nullish,
        symbol_distribution=symbol_distribution,
        symbol_detected_count=symbol_detected_count,
        symbol_detected_ratio=safe_ratio(symbol_detected_count, non_nullish),
        missing_symbol_count=missing_symbol_count,
        missing_symbol_ratio=safe_ratio(missing_symbol_count, non_nullish, default=0.0),
        dominant_symbol=dominant_symbol,
        dominant_symbol_ratio=safe_ratio(dominant_count, non_nullish),
        has_mixed_symbols=len(symbol_distribution) > 1,
    )


def _symbol_base_profile_fields(
    coverage: SymbolCoverageStats,
    parse_stats: DecimalParseStats,
) -> SymbolBaseProfileFields:
    return SymbolBaseProfileFields(
        symbol_distribution=coverage.symbol_distribution,
        symbol_detected_count=coverage.symbol_detected_count,
        symbol_detected_ratio=coverage.symbol_detected_ratio,
        missing_symbol_count=coverage.missing_symbol_count,
        missing_symbol_ratio=coverage.missing_symbol_ratio,
        dominant_symbol=coverage.dominant_symbol,
        dominant_symbol_ratio=coverage.dominant_symbol_ratio,
        has_mixed_symbols=coverage.has_mixed_symbols,
        parse_match_count=parse_stats.parse_match_count,
        parse_match_ratio=parse_stats.parse_match_ratio,
        comma_decimal_count=parse_stats.comma_decimal_count,
        dot_decimal_count=parse_stats.dot_decimal_count,
        mixed_number_format_detected=parse_stats.mixed_number_format_detected,
        max_scale=parse_stats.max_scale,
        max_integer_digits=parse_stats.max_integer_digits,
    )


def _build_currency_profile(
    parse_stats: DecimalParseStats,
    coverage: SymbolCoverageStats,
    metrics: CurrencyColumnMetrics,
) -> CurrencyColumnProfile:
    base_fields = _symbol_base_profile_fields(coverage, parse_stats)
    position_distribution = metrics.symbol_position_distribution
    dominant_position, dominant_position_count = _dominant_count(position_distribution)
    token_form_distribution = _build_token_form_distribution(coverage.symbol_distribution)
    dominant_form, dominant_form_count = _dominant_count(token_form_distribution)
    non_nullish = coverage.non_nullish_count
    return CurrencyColumnProfile(
        symbol_position_distribution=position_distribution,
        dominant_symbol_position=dominant_position,
        dominant_symbol_position_ratio=safe_ratio(dominant_position_count, non_nullish),
        has_mixed_symbol_positions=len(position_distribution) > 1,
        currency_token_form_distribution=token_form_distribution,
        dominant_currency_token_form=dominant_form,
        dominant_currency_token_form_ratio=safe_ratio(dominant_form_count, non_nullish),
        has_mixed_currency_token_forms=len(token_form_distribution) > 1,
        **base_fields,
    )


def _build_accounting_profile(
    parse_stats: DecimalParseStats,
    coverage: SymbolCoverageStats,
    metrics: AccountingColumnMetrics,
) -> AccountingColumnProfile:
    base_fields = _symbol_base_profile_fields(coverage, parse_stats)
    sign_distribution = metrics.sign_notation_distribution
    dominant_sign, dominant_sign_count = _dominant_count(sign_distribution)
    non_nullish = coverage.non_nullish_count
    unsigned_count = sign_distribution.get("unsigned", 0)
    return AccountingColumnProfile(
        sign_notation_distribution=sign_distribution,
        dominant_sign_notation=dominant_sign,
        dominant_sign_notation_ratio=safe_ratio(dominant_sign_count, non_nullish),
        has_mixed_sign_notations=len(sign_distribution) > 1,
        negative_marker_distribution=metrics.negative_marker_distribution,
        positive_marker_distribution=metrics.positive_marker_distribution,
        parentheses_negative_count=sign_distribution.get("parentheses", 0),
        leading_sign_count=sign_distribution.get("leading_sign", 0),
        trailing_sign_count=sign_distribution.get("trailing_sign", 0),
        explicit_sign_count=non_nullish - unsigned_count,
        unsigned_non_nullish_count=unsigned_count,
        **base_fields,
    )


def compute_symbol_column_profile(
    config: CurrencyColumnConfig | AccountingColumnConfig,
    counts: ColumnCounts,
    parse_stats: DecimalParseStats,
    metrics: SymbolColumnMetrics,
) -> CurrencyColumnProfile | AccountingColumnProfile:
    """Combine batched monetary metrics and parse stats for one symbol-bearing column."""
    coverage = _build_symbol_coverage_stats(counts, metrics)
    # Config remains the authoritative semantic type. Metrics are derived from the
    # mixed batch query and are only cross-checked here to catch impossible mismatches.
    if isinstance(config, CurrencyColumnConfig):
        if not isinstance(metrics, CurrencyColumnMetrics):
            raise TypeError("Currency columns require CurrencyColumnMetrics")
        return _build_currency_profile(parse_stats, coverage, metrics)
    if not isinstance(metrics, AccountingColumnMetrics):
        raise TypeError("Accounting columns require AccountingColumnMetrics")
    return _build_accounting_profile(parse_stats, coverage, metrics)
