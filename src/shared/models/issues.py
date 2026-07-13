"""Issue contract emitted by profiling and consumed by the decision gate and API.

Issues are a discriminated union on ``code``; each code fixes the shape of its
``evidence``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from shared.models.base import MainModel


class IssueSeverity(StrEnum):
    """Severity used for normalization issues."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class IssueBase(MainModel):
    """Fields carried by every issue.

    Severity varies per instance, not per code: IDENTIFIER_DUPLICATES is an ERROR on a
    primary key and a WARNING on any other identifier kind.
    """

    severity: IssueSeverity
    message: str


class ColumnIssueBase(IssueBase):
    """An issue attributable to one column, named by ``location``."""

    location: str


class PreambleRowsSkippedEvidence(MainModel):
    """Rows dropped at ingestion because they precede the header row."""

    skipped_count: int
    header_row_index: int


class PreambleRowsSkippedIssue(IssueBase):
    """Rows above the header row were skipped as preamble."""

    code: Literal["PREAMBLE_ROWS_SKIPPED"] = "PREAMBLE_ROWS_SKIPPED"
    evidence: PreambleRowsSkippedEvidence


class MultiplePrimaryKeysEvidence(MainModel):
    """The columns declared ``identifier_kind="primary"``."""

    columns: list[str]


class MultiplePrimaryKeysIssue(IssueBase):
    """More than one column is declared a primary key."""

    code: Literal["MULTIPLE_PRIMARY_KEYS"] = "MULTIPLE_PRIMARY_KEYS"
    evidence: MultiplePrimaryKeysEvidence


class IdentifierDuplicatesEvidence(MainModel):
    """Duplicate counts for an identifier column."""

    is_primary_key: bool
    duplicate_count: int
    distinct_count: int
    uniqueness_ratio: float


class IdentifierDuplicatesIssue(ColumnIssueBase):
    """An identifier column contains duplicate values."""

    code: Literal["IDENTIFIER_DUPLICATES"] = "IDENTIFIER_DUPLICATES"
    evidence: IdentifierDuplicatesEvidence


class MixedCurrencyEvidence(MainModel):
    """Distribution of the currency symbols found in one column."""

    symbols: list[str]
    symbol_detected_ratio: float
    dominant_symbol: str | None
    dominant_symbol_ratio: float


class MixedCurrencyIssue(ColumnIssueBase):
    """A currency or accounting column carries more than one symbol."""

    code: Literal["MIXED_CURRENCY"] = "MIXED_CURRENCY"
    evidence: MixedCurrencyEvidence


class MixedNumberFormatEvidence(MainModel):
    """Counts of each decimal notation found in one column."""

    comma_decimal_count: int
    dot_decimal_count: int


class MixedNumberFormatIssue(ColumnIssueBase):
    """A numeric column carries both european and western decimal notation."""

    code: Literal["MIXED_NUMBER_FORMAT"] = "MIXED_NUMBER_FORMAT"
    evidence: MixedNumberFormatEvidence


NormalizationIssue = Annotated[
    PreambleRowsSkippedIssue
    | MultiplePrimaryKeysIssue
    | IdentifierDuplicatesIssue
    | MixedCurrencyIssue
    | MixedNumberFormatIssue,
    Field(discriminator="code"),
]
