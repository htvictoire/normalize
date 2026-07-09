"""Row-level sampling for the AI inference strategy."""

from __future__ import annotations

from suggestion.ai.constants import DEFAULT_SAMPLE_ROW_COUNT


def sample_inference_rows(
    rows: list[list[str]],
    row_count: int = DEFAULT_SAMPLE_ROW_COUNT,
) -> list[list[str]]:
    """Return up to `row_count` whole rows, preserving row structure for cross-column context."""
    return rows[:row_count]
