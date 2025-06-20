"""Per-column declared parse configuration for no-guessing normalization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import duckdb

from normalize.core.column_positions import normalize_position_key
from normalize.core.numeric_formats import validate_grouping_style, validate_separator_pair

_DATE_DIRECTIVE_PATTERN = re.compile(r"%(?!%)[-_0^#]?[A-Za-z]")
_DATE_FORMAT_EXCEL_SERIAL = "EXCEL_SERIAL"

ColumnType = Literal["string", "boolean", "integer", "decimal", "currency", "date"]


@dataclass(frozen=True)
class StringColumnConfig:
    """Declared string column configuration."""

    type: Literal["string"] = "string"


@dataclass(frozen=True)
class BooleanColumnConfig:
    """Declared boolean column configuration."""

    type: Literal["boolean"] = "boolean"


@dataclass(frozen=True)
class IntegerColumnConfig:
    """Declared integer column configuration."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: str
    type: Literal["integer"] = "integer"


@dataclass(frozen=True)
class DecimalColumnConfig:
    """Declared decimal column configuration."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: str
    allow_leading_decimal_point: bool
    type: Literal["decimal"] = "decimal"


@dataclass(frozen=True)
class CurrencyColumnConfig:
    """Declared currency column configuration."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: str
    allow_leading_decimal_point: bool
    type: Literal["currency"] = "currency"


@dataclass(frozen=True)
class DateColumnConfig:
    """Declared date column configuration."""

    date_format: str
    type: Literal["date"] = "date"


ColumnConfig = (
    StringColumnConfig
    | BooleanColumnConfig
    | IntegerColumnConfig
    | DecimalColumnConfig
    | CurrencyColumnConfig
    | DateColumnConfig
)

ColumnConfigInput = ColumnConfig | Mapping[str, Any]


def column_config_type(config: ColumnConfig) -> ColumnType:
    """Return the discriminant type string for one column config."""
    return config.type


def normalize_column_config_map(
    column_config: Mapping[str, ColumnConfigInput],
) -> dict[str, ColumnConfig]:
    """Normalize position-keyed column config payloads into strict dataclasses."""
    normalized: dict[str, ColumnConfig] = {}
    for raw_key, raw_value in column_config.items():
        if not isinstance(raw_key, str):
            raise TypeError(f"column_config key must be a string, got {type(raw_key).__name__}")
        position_key = normalize_position_key(raw_key)
        field_name = f"column_config[{raw_key!r}]"
        normalized[position_key] = _normalize_column_config(raw_value, field_name=field_name)
    return normalized


def column_config_to_dict(config: ColumnConfig) -> dict[str, Any]:
    """Serialize one strict column config dataclass to a deterministic dict."""
    if isinstance(config, StringColumnConfig):
        return {"type": "string"}
    if isinstance(config, BooleanColumnConfig):
        return {"type": "boolean"}
    if isinstance(config, IntegerColumnConfig):
        return {
            "type": "integer",
            "decimal_separator": config.decimal_separator,
            "thousand_separator": config.thousand_separator,
            "grouping_style": config.grouping_style,
        }
    if isinstance(config, DecimalColumnConfig):
        return {
            "type": "decimal",
            "decimal_separator": config.decimal_separator,
            "thousand_separator": config.thousand_separator,
            "grouping_style": config.grouping_style,
            "allow_leading_decimal_point": config.allow_leading_decimal_point,
        }
    if isinstance(config, CurrencyColumnConfig):
        return {
            "type": "currency",
            "decimal_separator": config.decimal_separator,
            "thousand_separator": config.thousand_separator,
            "grouping_style": config.grouping_style,
            "allow_leading_decimal_point": config.allow_leading_decimal_point,
        }
    if isinstance(config, DateColumnConfig):
        return {
            "type": "date",
            "date_format": config.date_format,
        }
    raise TypeError(f"unsupported ColumnConfig value: {type(config).__name__}")


def serialize_column_config_map(
    column_config: Mapping[str, ColumnConfig],
) -> dict[str, dict[str, Any]]:
    """Serialize normalized position-keyed column config mapping."""
    return {
        position_key: column_config_to_dict(spec)
        for position_key, spec in column_config.items()
    }


def _normalize_column_config(raw: ColumnConfigInput, *, field_name: str) -> ColumnConfig:
    if isinstance(raw, Mapping):
        return _normalize_column_config_mapping(raw, field_name=field_name)
    return _normalize_column_config_dataclass(raw, field_name=field_name)


def _normalize_column_config_dataclass(raw: ColumnConfigInput, *, field_name: str) -> ColumnConfig:
    if isinstance(raw, StringColumnConfig):
        result: ColumnConfig = StringColumnConfig()
    elif isinstance(raw, BooleanColumnConfig):
        result = BooleanColumnConfig()
    elif isinstance(raw, IntegerColumnConfig):
        result = IntegerColumnConfig(
            decimal_separator=raw.decimal_separator,
            thousand_separator=raw.thousand_separator,
            grouping_style=_normalize_grouping_style(raw.grouping_style, field_name=field_name),
        )
    elif isinstance(raw, DecimalColumnConfig):
        _validate_leading_decimal_flag(
            raw.allow_leading_decimal_point,
            field_name=f"{field_name}.allow_leading_decimal_point",
        )
        result = DecimalColumnConfig(
            decimal_separator=raw.decimal_separator,
            thousand_separator=raw.thousand_separator,
            grouping_style=_normalize_grouping_style(raw.grouping_style, field_name=field_name),
            allow_leading_decimal_point=raw.allow_leading_decimal_point,
        )
    elif isinstance(raw, CurrencyColumnConfig):
        _validate_leading_decimal_flag(
            raw.allow_leading_decimal_point,
            field_name=f"{field_name}.allow_leading_decimal_point",
        )
        result = CurrencyColumnConfig(
            decimal_separator=raw.decimal_separator,
            thousand_separator=raw.thousand_separator,
            grouping_style=_normalize_grouping_style(raw.grouping_style, field_name=field_name),
            allow_leading_decimal_point=raw.allow_leading_decimal_point,
        )
    elif isinstance(raw, DateColumnConfig):
        format_string = _normalize_date_format(raw.date_format, field_name=field_name)
        result = DateColumnConfig(date_format=format_string)
    else:
        raise TypeError(f"{field_name} must be a mapping or ColumnConfig dataclass")
    return result


def _normalize_column_config_mapping(raw: Mapping[str, Any], *, field_name: str) -> ColumnConfig:
    raw_type = raw.get("type")
    if not isinstance(raw_type, str):
        raise TypeError(f"{field_name}.type must be a string")
    normalized_type = raw_type.strip().lower()

    if normalized_type == "string":
        _assert_exact_keys(raw, required_keys={"type"}, field_name=field_name)
        result: ColumnConfig = StringColumnConfig()
    elif normalized_type == "boolean":
        _assert_exact_keys(raw, required_keys={"type"}, field_name=field_name)
        result = BooleanColumnConfig()
    elif normalized_type == "integer":
        _assert_exact_keys(
            raw,
            required_keys={"type", "decimal_separator", "thousand_separator", "grouping_style"},
            field_name=field_name,
        )
        decimal_separator, thousand_separator, grouping_style = _read_numeric_fields(
            raw, field_name=field_name
        )
        result = IntegerColumnConfig(
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
        )
    elif normalized_type in {"decimal", "currency"}:
        _assert_exact_keys(
            raw,
            required_keys={
                "type",
                "decimal_separator",
                "thousand_separator",
                "grouping_style",
                "allow_leading_decimal_point",
            },
            field_name=field_name,
        )
        decimal_separator, thousand_separator, grouping_style = _read_numeric_fields(
            raw, field_name=field_name
        )
        allow_leading_decimal_point = raw["allow_leading_decimal_point"]
        _validate_leading_decimal_flag(
            allow_leading_decimal_point,
            field_name=f"{field_name}.allow_leading_decimal_point",
        )
        if normalized_type == "decimal":
            result = DecimalColumnConfig(
                decimal_separator=decimal_separator,
                thousand_separator=thousand_separator,
                grouping_style=grouping_style,
                allow_leading_decimal_point=allow_leading_decimal_point,
            )
        else:
            result = CurrencyColumnConfig(
                decimal_separator=decimal_separator,
                thousand_separator=thousand_separator,
                grouping_style=grouping_style,
                allow_leading_decimal_point=allow_leading_decimal_point,
            )
    elif normalized_type == "date":
        _assert_exact_keys(raw, required_keys={"type", "date_format"}, field_name=field_name)
        date_format = raw["date_format"]
        if not isinstance(date_format, str):
            raise TypeError(f"{field_name}.date_format must be a string")
        normalized_format = _normalize_date_format(date_format, field_name=field_name)
        result = DateColumnConfig(date_format=normalized_format)
    else:
        raise ValueError(
            f"{field_name}.type must be one of: "
            "string, boolean, integer, decimal, currency, date"
        )
    return result


def _assert_exact_keys(
    raw: Mapping[str, Any],
    *,
    required_keys: set[str],
    field_name: str,
) -> None:
    missing = sorted(required_keys - set(raw))
    if missing:
        raise ValueError(f"{field_name} missing required keys: {', '.join(missing)}")
    unexpected = sorted(set(raw) - required_keys)
    if unexpected:
        raise ValueError(f"{field_name} has unexpected keys: {', '.join(unexpected)}")


def _read_numeric_fields(raw: Mapping[str, Any], *, field_name: str) -> tuple[str, str, str]:
    decimal_separator = raw["decimal_separator"]
    thousand_separator = raw["thousand_separator"]
    grouping_style = raw["grouping_style"]
    if not isinstance(decimal_separator, str):
        raise TypeError(f"{field_name}.decimal_separator must be a string")
    if not isinstance(thousand_separator, str):
        raise TypeError(f"{field_name}.thousand_separator must be a string")
    if not isinstance(grouping_style, str):
        raise TypeError(f"{field_name}.grouping_style must be a string")

    validate_separator_pair(decimal_separator, thousand_separator, field_prefix=field_name)
    normalized_grouping_style = _normalize_grouping_style(grouping_style, field_name=field_name)
    return decimal_separator, thousand_separator, normalized_grouping_style


def _normalize_grouping_style(grouping_style: str, *, field_name: str) -> str:
    return validate_grouping_style(
        grouping_style,
        field_name=f"{field_name}.grouping_style",
    )


def _validate_leading_decimal_flag(value: Any, *, field_name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")


def _normalize_date_format(format_string: str, *, field_name: str) -> str:
    normalized = format_string.strip()
    if not normalized:
        raise ValueError(f"{field_name}.date_format must be a non-empty format string")
    if normalized == _DATE_FORMAT_EXCEL_SERIAL:
        return normalized
    if _DATE_DIRECTIVE_PATTERN.search(normalized) is None:
        raise ValueError(
            f"{field_name}.date_format must contain at least one strptime directive"
        )
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("SELECT TRY_STRPTIME('', ?)", [normalized]).fetchone()
    except Exception as exc:  # pragma: no cover - exact exception type is duckdb-bound
        raise ValueError(
            f"{field_name}.date_format contains invalid DuckDB strptime directives"
        ) from exc
    finally:
        conn.close()
    return normalized
