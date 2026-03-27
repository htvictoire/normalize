"""All constants for the suggestion package."""

from __future__ import annotations

from shared.models.operation import TraceMode

from suggestion.models import NumericCandidate

# ---------------------------------------------------------------------------
# Source format inference
# ---------------------------------------------------------------------------

# Maximum bytes read from the file. All inference runs on this prefix.
FILE_SAMPLE_BYTES = 4 * 1024 * 1024

# Product budget: JSON sources with roughly 1000 objects should stay within 1 GiB.
# That yields an explicit per-object budget of about 1 MiB for the first row.
JSON_FIRST_OBJECT_MAX_BYTES = 1024 * 1024

# Delimiter candidates, in order of prevalence.
DELIMITER_CANDIDATES = [",", ";", "\t", "|"]

# Total rows read from the top of the file when scanning for the header row.
HEADER_SCAN_ROWS = 15

# Subsequent rows inspected after each header candidate to measure data
# numeric density. The header scores highest because it has near-zero
# numeric density compared to the data rows that follow it.
HEADER_SCORE_LOOKAHEAD = 5

# ---------------------------------------------------------------------------
# Sample data display
# ---------------------------------------------------------------------------

# Maximum raw rows returned for display.
DISPLAY_RAW_ROWS = 15

# Maximum non-null values collected per column for type preview display.
DISPLAY_VALUES_PER_COLUMN = 10

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

# ---------------------------------------------------------------------------
# Numeric grouping
# ---------------------------------------------------------------------------

GROUP_FIRST_MAX_DIGITS = 3
GROUP_WESTERN_SIZE = 3
GROUP_INDIAN_MIDDLE_SIZE = 2
GROUP_INDIAN_TWO_GROUP_CASE = 2

# Minimum fraction of sampled values with a leading decimal point (e.g. ".5")
# for the pattern to be recorded as intentional in the suggested config
# (allow_leading_decimal_point).
LEADING_DECIMAL_MIN_RATIO = 0.05

# ---------------------------------------------------------------------------
# Default operation config
# ---------------------------------------------------------------------------
# Pre-populate the suggested InstanceConfig after suggestion.
# The user can override any of these at confirm time.

DEFAULT_ASSIGN_INDICES: bool = False
DEFAULT_DROP_EMPTY_ROWS: bool = True
DEFAULT_EMIT_RAW_ROW: bool = False
DEFAULT_FULL_RAW_ROW: bool = False
DEFAULT_EMIT_PARSE_ISSUES: bool = False
DEFAULT_INCLUDE_UNIQUE_RATIO: bool = True
DEFAULT_INCLUDE_PER_COLUMN_PARSE_ERROR_COUNTS: bool = True
DEFAULT_APPROXIMATE_UNIQUE: bool = False
DEFAULT_TRACE_MODE: TraceMode = "sparse"
DEFAULT_DECISION_READY: float = 95.0
DEFAULT_DECISION_WARNING: float = 85.0

# ---------------------------------------------------------------------------
# Null tokens
# ---------------------------------------------------------------------------

# Known sentinel strings commonly used to represent missing values.
NULL_TOKEN_CANDIDATES = frozenset({
    "n/a", "na", "null", "none", "nan", "nil", "-", "--", "---", "?", "missing",
})

# ---------------------------------------------------------------------------
# Numeric candidates
# ---------------------------------------------------------------------------

# All candidate numeric formatting layouts scored during type inference.
NUMERIC_CANDIDATES = (
    NumericCandidate(decimal_separator=".", thousand_separator="", grouping_style="western"),
    NumericCandidate(decimal_separator=",", thousand_separator="", grouping_style="western"),
    NumericCandidate(decimal_separator=".", thousand_separator=",", grouping_style="western"),
    NumericCandidate(decimal_separator=",", thousand_separator=".", grouping_style="western"),
    NumericCandidate(decimal_separator=".", thousand_separator=",", grouping_style="indian"),
    NumericCandidate(decimal_separator=",", thousand_separator=".", grouping_style="indian"),
    NumericCandidate(decimal_separator=".", thousand_separator="'", grouping_style="western"),
)
