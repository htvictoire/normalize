"""Issues raised from a suggestion's confidence scores."""

from __future__ import annotations

from shared.models.issues import (
    IssueSeverity,
    LowConfidenceEvidence,
    LowConfidenceIssue,
    LowConfidenceItem,
)
from shared.models.suggestion import SuggestionConfidence, SuggestionDisplay


def low_confidence_items(
    confidence: SuggestionConfidence,
    display: SuggestionDisplay,
    threshold: float,
) -> list[LowConfidenceItem]:
    """Return every scored inference below ``threshold`` — columns, delimiter, header."""
    items: list[LowConfidenceItem] = []
    if confidence.delimiter is not None and confidence.delimiter < threshold:
        items.append(
            LowConfidenceItem(target="delimiter", kind="delimiter", confidence=confidence.delimiter)
        )
    if confidence.header is not None and confidence.header < threshold:
        items.append(
            LowConfidenceItem(target="header", kind="header", confidence=confidence.header)
        )
    for position, score in confidence.column_config.items():
        if score < threshold:
            column = display.columns.get(position)
            name = column.label if column is not None else position
            items.append(LowConfidenceItem(target=name, kind="column", confidence=score))
    return items


def build_low_confidence_issue(
    confidence: SuggestionConfidence,
    display: SuggestionDisplay,
    threshold: float,
) -> LowConfidenceIssue | None:
    """Build the warning issue for a suggestion's sub-threshold inferences, or None."""
    items = low_confidence_items(confidence, display, threshold)
    if not items:
        return None
    return LowConfidenceIssue(
        severity=IssueSeverity.WARNING,
        message=f"{len(items)} inference(s) scored below confidence {threshold}",
        evidence=LowConfidenceEvidence(items=items, threshold=threshold),
    )
