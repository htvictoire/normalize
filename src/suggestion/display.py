"""Per-column display value extraction from pre-parsed rows."""

from __future__ import annotations

from suggestion.constants import DISPLAY_VALUES_PER_COLUMN


def read_sample_values(
    rows: list[list[str]],
    position_to_name: dict[str, str],
    limit: int = DISPLAY_VALUES_PER_COLUMN,
) -> dict[str, list[str]]:
    """Return up to ``limit`` non-empty values per column, keyed by position."""
    positions = list(position_to_name.keys())
    result: dict[str, list[str]] = {pos: [] for pos in positions}

    for row in rows:
        all_full = True
        for i, pos in enumerate(positions):
            if len(result[pos]) >= limit:
                continue
            all_full = False
            raw = row[i].strip()
            if raw:
                result[pos].append(raw)
        if all_full:
            break

    return result
