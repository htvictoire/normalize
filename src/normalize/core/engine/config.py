"""Engine runtime configuration contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

import duckdb

from normalize.core.column_positions import normalize_position_key
from normalize.stages.ingestion.contracts import HeaderMode

_DATE_DIRECTIVE_PATTERN = re.compile(r"%(?!%)[-_0^#]?[A-Za-z]")


@dataclass(frozen=True)
class EngineConfig:
    """Runtime config for Phase 1 engine orchestration."""

    rules_version: str
    duckdb_path: str
    header_mode: HeaderMode
    header_row_index: int | None
    encoding: str
    delimiter: str
    decimal_separator: str
    thousand_separator: str
    allow_leading_decimal_point: bool
    date_formats: Mapping[str, str]
    null_tokens: tuple[str, ...]
    boolean_true_tokens: tuple[str, ...]
    boolean_false_tokens: tuple[str, ...]
    type_inference_numeric_threshold: float
    type_inference_boolean_threshold: float
    type_inference_currency_threshold: float
    profiling_currency_candidate_threshold: float
    assign_indices: bool
    drop_empty_rows: bool
    full_raw_row: bool
    emit_raw_row: bool
    emit_parse_issues: bool
    include_unique_ratio: bool
    include_per_column_parse_error_counts: bool
    approximate_unique: bool
    decision_ready_threshold: float
    decision_warning_threshold: float
    trace_mode: str  # "full" or "sparse"
    threads: int

    def __post_init__(self) -> None:
        decimal_separator = self.decimal_separator
        thousand_separator = self.thousand_separator
        if len(decimal_separator) != 1:
            raise ValueError("decimal_separator must be exactly one character")
        if thousand_separator and len(thousand_separator) != 1:
            raise ValueError("thousand_separator must be empty or exactly one character")
        if thousand_separator and decimal_separator == thousand_separator:
            raise ValueError("decimal_separator and thousand_separator must differ")
        if not isinstance(self.allow_leading_decimal_point, bool):
            raise TypeError("allow_leading_decimal_point must be a boolean")
        _validate_ratio_threshold(
            "type_inference_numeric_threshold", self.type_inference_numeric_threshold
        )
        _validate_ratio_threshold(
            "type_inference_boolean_threshold", self.type_inference_boolean_threshold
        )
        _validate_ratio_threshold(
            "type_inference_currency_threshold", self.type_inference_currency_threshold
        )
        _validate_ratio_threshold(
            "profiling_currency_candidate_threshold", self.profiling_currency_candidate_threshold
        )

        normalized_date_formats: dict[str, str] = {}
        for raw_key, format_string in self.date_formats.items():
            if not isinstance(raw_key, str):
                raise TypeError(f"date_formats key must be a string, got {type(raw_key).__name__}")
            key = normalize_position_key(raw_key)
            if not isinstance(format_string, str) or not format_string.strip():
                raise ValueError(f"date_formats[{raw_key!r}] must be a non-empty format string")
            normalized_date_formats[key] = format_string
        _validate_date_formats_with_duckdb(normalized_date_formats)
        object.__setattr__(self, "date_formats", normalized_date_formats)


def _validate_date_formats_with_duckdb(date_formats: Mapping[str, str]) -> None:
    if not date_formats:
        return

    conn = duckdb.connect(":memory:")
    try:
        for position_key, format_string in date_formats.items():
            if format_string == "EXCEL_SERIAL":
                continue
            if _DATE_DIRECTIVE_PATTERN.search(format_string) is None:
                raise ValueError(
                    f"date_formats[{position_key!r}] must contain at least one strptime directive"
                )
            try:
                conn.execute("SELECT TRY_STRPTIME('', ?)", [format_string]).fetchone()
            except Exception as exc:  # pragma: no cover - exact exception type is duckdb-bound
                raise ValueError(
                    f"date_formats[{position_key!r}] contains invalid DuckDB strptime directives"
                ) from exc
    finally:
        conn.close()


def _validate_ratio_threshold(field_name: str, value: float) -> None:
    if value <= 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be in (0, 1]")
