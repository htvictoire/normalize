"""Shared issue model used by profile and normalize phases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IssueSeverity(StrEnum):
    """Severity used for normalization issues."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class NormalizationIssue:
    """Structured issue shape used in quality/decision/profile stages."""

    code: str
    severity: IssueSeverity
    message: str
    location: str | None = None
    evidence: dict[str, Any] | None = None
    pattern_context: dict[str, Any] | None = None
