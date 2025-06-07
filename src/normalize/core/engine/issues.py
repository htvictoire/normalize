"""Issue construction helpers for engine outputs."""

from __future__ import annotations

from typing import Any

from normalize.core.domain import IssueSeverity, NormalizationIssue

ISSUE_CODE_PARSE_ERRORS_PRESENT = "PARSE_ERRORS_PRESENT"
ISSUE_CODE_SEPARATOR_MISMATCH = "SEPARATOR_MISMATCH"
ISSUE_CODE_UNKNOWN_COLUMN_REFERENCE = "UNKNOWN_COLUMN_REFERENCE"


def build_issues(quality_result: dict[str, Any]) -> list[NormalizationIssue]:
    """Construct run issues from stage outputs."""
    issues: list[NormalizationIssue] = []
    parse_errors = int(quality_result.get("total_parse_error_cells", 0))
    if parse_errors > 0:
        issues.append(
            NormalizationIssue(
                code=ISSUE_CODE_PARSE_ERRORS_PRESENT,
                severity=IssueSeverity.WARNING,
                message=f"{parse_errors} parse error cells detected",
            )
        )
    return issues


def build_separator_mismatch_issue(
    *,
    column_name: str,
    decimal_separator: str,
    thousand_separator: str,
    numeric_threshold: float,
    declared_decimal_ratio: float,
    swapped_decimal_ratio: float,
) -> NormalizationIssue:
    """Build a warning when swapped separators match the column better."""
    return NormalizationIssue(
        code=ISSUE_CODE_SEPARATOR_MISMATCH,
        severity=IssueSeverity.WARNING,
        message=(
            f"Column {column_name!r} appears numeric with swapped separators "
            f"(declared decimal={decimal_separator!r}, thousand={thousand_separator!r})"
        ),
        location=column_name,
        evidence={
            "numeric_threshold": numeric_threshold,
            "declared_decimal_ratio": declared_decimal_ratio,
            "swapped_decimal_ratio": swapped_decimal_ratio,
            "declared_separators": {
                "decimal_separator": decimal_separator,
                "thousand_separator": thousand_separator,
            },
            "suggested_separators": {
                "decimal_separator": thousand_separator,
                "thousand_separator": decimal_separator,
            },
        },
    )


def build_unknown_column_reference_issue(
    position_key: str, column_count: int
) -> NormalizationIssue:
    """Build warning for position keys outside CSV column bounds."""
    message = (
        f"date_formats position key {position_key!r} "
        f"is out of range for {column_count} columns"
    )
    return NormalizationIssue(
        code=ISSUE_CODE_UNKNOWN_COLUMN_REFERENCE,
        severity=IssueSeverity.WARNING,
        message=message,
        location=position_key,
        evidence={"position_key": position_key, "column_count": column_count},
    )


def issue_to_dict(issue: NormalizationIssue) -> dict[str, Any]:
    """Convert structured issue to serialized payload."""
    payload: dict[str, Any] = {
        "code": issue.code,
        "severity": issue.severity.value,
        "message": issue.message,
    }
    if issue.location is not None:
        payload["location"] = issue.location
    if issue.evidence is not None:
        payload["evidence"] = issue.evidence
    if issue.pattern_context is not None:
        payload["pattern_context"] = issue.pattern_context
    return payload
