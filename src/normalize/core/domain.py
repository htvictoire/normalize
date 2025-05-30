"""Core domain enums and issue model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    """Run terminal and non-terminal statuses used by decision evaluation."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class IssueSeverity(StrEnum):
    """Severity used for normalization issues."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class NormalizationIssue:
    """Structured issue shape used in quality/decision stages."""

    code: str
    severity: IssueSeverity
    message: str
    location: str | None = None
    evidence: dict[str, Any] | None = None
    pattern_context: dict[str, Any] | None = None
