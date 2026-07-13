"""Profiling-phase constants."""

from __future__ import annotations

# Issue codes emitted by the profiling pipeline.
# MIXED_CURRENCY: a currency/accounting column contains more than one distinct symbol.
ISSUE_CODE_MIXED_CURRENCY = "MIXED_CURRENCY"
# MIXED_NUMBER_FORMAT: a numeric column carries both european and western decimal
# notation. Informational — each value is parsed on its own notation.
ISSUE_CODE_MIXED_NUMBER_FORMAT = "MIXED_NUMBER_FORMAT"
# IDENTIFIER_DUPLICATES: an identifier column contains duplicate non-nullish values.
# ERROR on a primary key (a duplicate key is a broken contract), WARNING otherwise.
ISSUE_CODE_IDENTIFIER_DUPLICATES = "IDENTIFIER_DUPLICATES"
# MULTIPLE_PRIMARY_KEYS: more than one column is declared identifier_kind="primary".
ISSUE_CODE_MULTIPLE_PRIMARY_KEYS = "MULTIPLE_PRIMARY_KEYS"
