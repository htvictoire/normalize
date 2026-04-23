"""Pipeline duration estimation from row count."""

from __future__ import annotations

from suggestion.constants import PIPELINE_DURATION_TIERS


def estimate_pipeline_seconds(row_count: int) -> int:
    tiers = PIPELINE_DURATION_TIERS
    if row_count <= tiers[0][0]:
        return tiers[0][1]
    for i in range(1, len(tiers)):
        low_rows, low_secs = tiers[i - 1]
        high_rows, high_secs = tiers[i]
        if row_count <= high_rows:
            ratio = (row_count - low_rows) / (high_rows - low_rows)
            return round(low_secs + ratio * (high_secs - low_secs))
    low_rows, low_secs = tiers[-2]
    high_rows, high_secs = tiers[-1]
    ratio = (row_count - low_rows) / (high_rows - low_rows)
    return round(low_secs + ratio * (high_secs - low_secs))
