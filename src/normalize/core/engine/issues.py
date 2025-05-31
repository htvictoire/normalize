"""Issue construction helpers for engine outputs."""

from __future__ import annotations

from typing import Any

from normalize.core.domain import IssueSeverity, NormalizationIssue


def build_issues(quality_result: dict[str, Any]) -> list[NormalizationIssue]:
    """Construct run issues from stage outputs."""
    issues: list[NormalizationIssue] = []
    parse_errors = int(quality_result.get("total_parse_error_cells", 0))
    if parse_errors > 0:
        issues.append(
            NormalizationIssue(
                code="PARSE_ERRORS_PRESENT",
                severity=IssueSeverity.WARNING,
                message=f"{parse_errors} parse error cells detected",
            )
        )
    return issues


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
