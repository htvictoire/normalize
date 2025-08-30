"""All constants for the suggestion package."""

from __future__ import annotations

from suggestion.column_config.models import NumericCandidate

# ---------------------------------------------------------------------------
# Source format inference
# ---------------------------------------------------------------------------

# Maximum bytes read from the file. All inference runs on this prefix.
FILE_SAMPLE_BYTES = 4 * 1024 * 1024

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
DISPLAY_RAW_ROWS = 30

# Maximum non-null values collected per column for type preview display.
DISPLAY_VALUES_PER_COLUMN = 20

# ---------------------------------------------------------------------------
# Type inference sampling
# ---------------------------------------------------------------------------

# Number of rows fed to the DuckDB reservoir sampler for type inference.
INFERENCE_RESERVOIR_ROWS = 2000

# Maximum number of sampled values used per column during type inference.
INFERENCE_SAMPLES_PER_COLUMN = 256

# Random seed for the reservoir sampler, for reproducibility.
INFERENCE_SAMPLE_SEED = 42

# Minimum fraction of non-null sampled values that must match a candidate type
# before that type is accepted for a column.
TYPE_MATCH_MIN_RATIO = 0.80

# ---------------------------------------------------------------------------
# Boolean tokens
# ---------------------------------------------------------------------------

BOOLEAN_TRUE_TOKENS = {"1", "true", "yes"}
BOOLEAN_FALSE_TOKENS = {"0", "false", "no"}

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
NUMERIC_CANDIDATES: tuple[NumericCandidate, ...] = (
    NumericCandidate(decimal_separator=".", thousand_separator="", grouping_style="western"),
    NumericCandidate(decimal_separator=",", thousand_separator="", grouping_style="western"),
    NumericCandidate(decimal_separator=".", thousand_separator=",", grouping_style="western"),
    NumericCandidate(decimal_separator=",", thousand_separator=".", grouping_style="western"),
    NumericCandidate(decimal_separator=".", thousand_separator=",", grouping_style="indian"),
    NumericCandidate(decimal_separator=",", thousand_separator=".", grouping_style="indian"),
)
