"""Profiling-phase constants."""

from __future__ import annotations

# Issue codes emitted by the profiling pipeline.
# MIXED_CURRENCY: a currency/accounting column contains more than one distinct symbol.
ISSUE_CODE_MIXED_CURRENCY = "MIXED_CURRENCY"
# MIXED_NUMBER_FORMAT: a numeric column carries both european and western decimal
# notation. Informational — each value is parsed on its own notation.
ISSUE_CODE_MIXED_NUMBER_FORMAT = "MIXED_NUMBER_FORMAT"
# IDENTIFIER_DUPLICATES: an identifier column contains duplicate non-nullish values.
ISSUE_CODE_IDENTIFIER_DUPLICATES = "IDENTIFIER_DUPLICATES"
