"""Issues raised from a suggestion's confidence scores."""

from __future__ import annotations

from shared.models.issues import (
    IssueSeverity,
    LowConfidenceEvidence,
    LowConfidenceIssue,
    LowConfidenceItem,
)
from shared.models.suggestion import LayoutConfidence, SuggestionDisplay


def low_confidence_items(
    layout: LayoutConfidence,
    column_confidence: dict[str, float],
    display: SuggestionDisplay,
    threshold: float,
) -> list[LowConfidenceItem]:
    """Return every scored inference below ``threshold`` — columns, delimiter, header."""
    items: list[LowConfidenceItem] = []
    if layout.delimiter is not None and layout.delimiter < threshold:
        items.append(
            LowConfidenceItem(target="delimiter", kind="delimiter", confidence=layout.delimiter)
        )
    if layout.header is not None and layout.header < threshold:
        items.append(
            LowConfidenceItem(target="header", kind="header", confidence=layout.header)
        )
    for position, score in column_confidence.items():
        if score < threshold:
            column = display.columns.get(position)
            name = column.label if column is not None else position
            items.append(LowConfidenceItem(target=name, kind="column", confidence=score))
    return items


def build_low_confidence_issue(
    layout: LayoutConfidence,
    column_confidence: dict[str, float],
    display: SuggestionDisplay,
    threshold: float,
) -> LowConfidenceIssue | None:
    """Build the warning issue for a suggestion's sub-threshold inferences, or None."""
    items = low_confidence_items(layout, column_confidence, display, threshold)
    if not items:
        return None
    return LowConfidenceIssue(
        severity=IssueSeverity.WARNING,
        message=f"{len(items)} inference(s) scored below confidence {threshold}",
        evidence=LowConfidenceEvidence(items=items, threshold=threshold),
    )
