"""Tunables for the rule-based (heuristic decision-tree) inference strategy."""

from __future__ import annotations

# Confidence reported for every rule-based inference. This strategy does not score its
# guesses; see _rule_based_confidence in pipeline.py.
RULE_BASED_CONFIDENCE = 0.5

# ---------------------------------------------------------------------------
# Source format inference (delimiter and header-row detection heuristics)
# ---------------------------------------------------------------------------

# Delimiter candidates, in order of prevalence.
DELIMITER_CANDIDATES = [",", ";", "\t", "|"]

# Total rows read from the top of the file when scanning for the header row.
HEADER_SCAN_ROWS = 15

# ---------------------------------------------------------------------------
# Type inference sampling
# ---------------------------------------------------------------------------

# Maximum number of sampled values used per column during type inference.
INFERENCE_SAMPLES_PER_COLUMN = 256

# Minimum fraction of non-null sampled values that must match a candidate type
# before that type is accepted for a column.
TYPE_MATCH_MIN_RATIO = 0.55

# Minimum match ratio for accounting and currency types. Currency symbol tokens
# are rare enough in non-numeric columns that ~10% match is a strong signal.
CURRENCY_MATCH_MIN_RATIO = 0.1

# Minimum match ratio for signed type. Sign markers can appear in non-numeric
# columns more readily than currency symbols, so this is tracked separately
# from CURRENCY_MATCH_MIN_RATIO to allow independent tuning.
SIGNED_MATCH_MIN_RATIO = 0.1

# Minimum match ratio for standardized-code types. Short string tokens can overlap
# ordinary categorical values, so code inference is intentionally stricter than
# generic type inference.
CODE_MATCH_MIN_RATIO = 0.95

# ---------------------------------------------------------------------------
# Boolean tokens
# ---------------------------------------------------------------------------

# Boolean tokens that are also integers, so not evidence of a boolean on their own.
# The full boolean vocabulary lives in ``shared.parsing.boolean``.
NUMERIC_BOOLEAN_TOKENS: frozenset[str] = frozenset({"0", "1"})
