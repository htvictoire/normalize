"""Type dispatcher for cell normalization SQL expressions."""

from __future__ import annotations

from shared.models.column import (
    BooleanColumnConfig,
    CategoricalColumnConfig,
    ColumnConfig,
    CountryCodeColumnConfig,
    CurrencyCodeColumnConfig,
    DateColumnConfig,
    DateTimeColumnConfig,
    DecimalSyntaxColumnConfig,
    EmailColumnConfig,
    IntegerColumnConfig,
    IpAddressColumnConfig,
    LanguageCodeColumnConfig,
    PhoneColumnConfig,
    StringColumnConfig,
    TimeColumnConfig,
    UrlColumnConfig,
)
from shared.parsing.normalizer import build_value_candidate_expr

from conversion.cells.exprs.ai_only import (
    build_categorical_exprs,
    build_email_exprs,
    build_ip_address_exprs,
    build_phone_exprs,
    build_url_exprs,
)
from conversion.cells.exprs.boolean import build_boolean_exprs
from conversion.cells.exprs.code import (
    build_country_code_exprs,
    build_currency_code_exprs,
    build_language_code_exprs,
)
from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.exprs.date import (
    build_date_exprs,
    build_datetime_exprs,
    build_time_exprs,
)
from conversion.cells.exprs.numeric import (
    build_decimal_exprs,
    build_integer_exprs,
)


def build_column_exprs(
    column_name: str,
    config: ColumnConfig,
    nullish_predicate: str,
    raw_value: str,
    normalized_raw_value: str,
) -> ColumnExprs:
    """Route to the appropriate type-specific expression builder."""
    if isinstance(config, StringColumnConfig):
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {raw_value} END"
        return ColumnExprs(parse_cte_entries=(), normalized_expr=normalized, issue_expr="NULL")

    issue_label = f"INVALID_{config.type.upper()}"

    if isinstance(config, BooleanColumnConfig):
        exprs = build_boolean_exprs(
            nullish_predicate,
            normalized_raw_value,
            true_tokens=config.true_tokens,
            false_tokens=config.false_tokens,
            issue_label=issue_label,
        )
    elif isinstance(config, DateColumnConfig):
        exprs = build_date_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            date_format=config.date_format,
            issue_label=issue_label,
        )
    elif isinstance(config, DateTimeColumnConfig):
        exprs = build_datetime_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            datetime_format=config.datetime_format,
            issue_label=issue_label,
        )
    elif isinstance(config, TimeColumnConfig):
        exprs = build_time_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            time_format=config.time_format,
            issue_label=issue_label,
        )
    elif isinstance(config, CountryCodeColumnConfig):
        exprs = build_country_code_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            code_format=config.code_format,
            issue_label=issue_label,
        )
    elif isinstance(config, CurrencyCodeColumnConfig):
        exprs = build_currency_code_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            issue_label=issue_label,
        )
    elif isinstance(config, LanguageCodeColumnConfig):
        exprs = build_language_code_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            code_format=config.code_format,
            issue_label=issue_label,
        )
    elif isinstance(config, CategoricalColumnConfig):
        exprs = build_categorical_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            value_map=config.value_map,
            unknown_value_policy=config.unknown_value_policy,
            issue_label=issue_label,
        )
    elif isinstance(config, EmailColumnConfig):
        exprs = build_email_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            issue_label=issue_label,
        )
    elif isinstance(config, UrlColumnConfig):
        exprs = build_url_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            issue_label=issue_label,
        )
    elif isinstance(config, IpAddressColumnConfig):
        exprs = build_ip_address_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            version=config.version,
            issue_label=issue_label,
        )
    elif isinstance(config, PhoneColumnConfig):
        exprs = build_phone_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            issue_label=issue_label,
        )
    elif isinstance(config, IntegerColumnConfig):
        exprs = build_integer_exprs(
            column_name,
            nullish_predicate,
            raw_value=raw_value,
            thousand_separator=config.thousand_separator,
            grouping_style=config.grouping_style,
            issue_label=issue_label,
        )
    elif isinstance(config, DecimalSyntaxColumnConfig):
        # Decimal-syntax types preprocess via the shared normalizer before matching/casting.
        candidate = build_value_candidate_expr(raw_value, config)
        exprs = build_decimal_exprs(
            column_name,
            nullish_predicate,
            raw_value=candidate,
            decimal_separator=config.decimal_separator,
            thousand_separator=config.thousand_separator,
            grouping_style=config.grouping_style,
            allow_leading_decimal_point=config.allow_leading_decimal_point,
            issue_label=issue_label,
        )
    else:
        raise TypeError(f"Unsupported column config type: {type(config).__name__}")

    return exprs
