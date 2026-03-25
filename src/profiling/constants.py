"""Profiling-phase constants."""

from __future__ import annotations

# Minimum swapped-separator match ratio that triggers a SEPARATOR_MISMATCH warning.
# When more than this fraction of non-nullish values match the pattern with decimal
# and thousand separators swapped, the declared separators are likely wrong.
NUMERIC_MISMATCH_THRESHOLD = 0.60
