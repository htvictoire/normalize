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

# Each pair is (true_token, false_token). Finding either side in the data
# causes both sides to be included in the suggested config.
BOOLEAN_TOKEN_PAIRS: tuple[tuple[str, str], ...] = (
    ("true", "false"),
    ("yes", "no"),
    ("1", "0"),
    ("t", "f"),
    ("y", "n"),
    ("on", "off"),
    ("active", "inactive"),
    ("enabled", "disabled"),
    ("checked", "unchecked"),
    ("pass", "fail"),
    ("ok", "nok"),
    ("paid", "unpaid"),
)

BOOLEAN_TRUE_TOKENS: frozenset[str] = frozenset(t for t, _ in BOOLEAN_TOKEN_PAIRS)
BOOLEAN_FALSE_TOKENS: frozenset[str] = frozenset(f for _, f in BOOLEAN_TOKEN_PAIRS)

# Boolean tokens that are also integers. Not evidence of a boolean on their own; still
# valid tokens for a column confirmed as boolean.
NUMERIC_BOOLEAN_TOKENS: frozenset[str] = frozenset({"0", "1"})

# ---------------------------------------------------------------------------
# Date formats
# ---------------------------------------------------------------------------

DATE_FORMAT_CANDIDATES = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
)

# Maps each format to its index in DATE_FORMAT_CANDIDATES — used as a tiebreaker
# so that equal-count formats resolve deterministically to the highest-priority format.
DATE_FORMAT_RANK: dict[str, int] = {fmt: i for i, fmt in enumerate(DATE_FORMAT_CANDIDATES)}

DATETIME_FORMAT_CANDIDATES = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
)

DATETIME_FORMAT_RANK: dict[str, int] = {
    fmt: i for i, fmt in enumerate(DATETIME_FORMAT_CANDIDATES)
}

TIME_FORMAT_CANDIDATES = (
    "%H:%M:%S",
    "%H:%M",
    "%I:%M:%S %p",
    "%I:%M %p",
)

TIME_FORMAT_RANK: dict[str, int] = {fmt: i for i, fmt in enumerate(TIME_FORMAT_CANDIDATES)}

# Minimum fraction of sampled values with a leading decimal point (e.g. ".5")
# for the pattern to be recorded as intentional in the suggested config
# (allow_leading_decimal_point).
LEADING_DECIMAL_MIN_RATIO = 0.05
