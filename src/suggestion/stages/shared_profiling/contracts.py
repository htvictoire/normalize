"""Contracts and constants for shared column profiling."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PROFILE_TABLE_NAME = "_column_profile_raw_input"
AUDIT_COLUMNS = {
    "_row_index",
    "_global_row_index",
    "_raw_row",
    "_parse_issues",
    "_parse_error_count",
}


@dataclass(frozen=True)
class ColumnProfile:
    """Profiled column counters and derived ratios."""

    column_name: str
    row_count: int
    non_empty_count: int
    bool_match_count: int
    int_match_count: int
    float_match_count: int
    swapped_float_match_count: int
    currency_match_count: int
    accounting_negative_match_count: int
    nullish_count: int

    @property
    def bool_ratio(self) -> float:
        return _safe_ratio(self.bool_match_count, self.non_empty_count)

    @property
    def int_ratio(self) -> float:
        return _safe_ratio(self.int_match_count, self.non_empty_count)

    @property
    def float_ratio(self) -> float:
        return _safe_ratio(self.float_match_count, self.non_empty_count)

    @property
    def decimal_ratio(self) -> float:
        return self.float_ratio

    @property
    def swapped_float_ratio(self) -> float:
        return _safe_ratio(self.swapped_float_match_count, self.non_empty_count)

    @property
    def swapped_decimal_ratio(self) -> float:
        return self.swapped_float_ratio

    @property
    def currency_ratio(self) -> float:
        return _safe_ratio(self.currency_match_count, self.non_empty_count)

    @property
    def accounting_negative_ratio(self) -> float:
        return _safe_ratio(self.accounting_negative_match_count, self.non_empty_count)

    @property
    def null_ratio(self) -> float:
        return _safe_ratio(self.nullish_count, self.row_count)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
