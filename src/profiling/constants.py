"""Profiling-phase constants."""

from __future__ import annotations

# Minimum swapped-separator match ratio that triggers a SEPARATOR_MISMATCH warning.
# When more than this fraction of non-nullish values match the pattern with decimal
# and thousand separators swapped, the declared separators are likely wrong.
NUMERIC_MISMATCH_THRESHOLD = 0.60

# Issue codes emitted by the profiling pipeline.
# MIXED_CURRENCY: a currency/accounting column contains more than one distinct symbol.
ISSUE_CODE_MIXED_CURRENCY = "MIXED_CURRENCY"
# SEPARATOR_MISMATCH: declared decimal/thousand separators appear swapped in the data.
ISSUE_CODE_SEPARATOR_MISMATCH = "SEPARATOR_MISMATCH"
