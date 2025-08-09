"""Constants used by suggestion inference and profiling."""

from __future__ import annotations

import re

from suggest.models import NumericCandidate

DEFAULT_SAMPLE_ROWS = 2000
DEFAULT_SAMPLES_PER_COLUMN = 256

BOOLEAN_TRUE_TOKENS = {"1", "true"}
BOOLEAN_FALSE_TOKENS = {"0", "false", "no"}

CURRENCY_SYMBOLS = "$€£¥₹₩₪₿₺₽₴₫₦₱₭₲₡"
CURRENCY_RE = re.compile(f"[{re.escape(CURRENCY_SYMBOLS)}]")

DATE_FORMAT_CANDIDATES = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
)

GROUP_FIRST_MAX_DIGITS = 3
GROUP_WESTERN_SIZE = 3
GROUP_INDIAN_MIDDLE_SIZE = 2
GROUP_INDIAN_TWO_GROUP_CASE = 2

# Minimum fraction of sampled values that must show a leading decimal point
# (e.g. ".5") before allow_leading_decimal_point is enabled for a column.
LEADING_DECIMAL_MIN_RATIO = 0.05

# Minimum number of evidenced numeric columns required to establish a
# file-level decimal separator for cross-column consistency correction.
CROSS_COLUMN_MAJORITY_MIN_EVIDENCED = 2

NUMERIC_CANDIDATES = (
    NumericCandidate(decimal_separator=".", thousand_separator="", grouping_style="western"),
    NumericCandidate(decimal_separator=",", thousand_separator="", grouping_style="western"),
    NumericCandidate(decimal_separator=".", thousand_separator=",", grouping_style="western"),
    NumericCandidate(decimal_separator=",", thousand_separator=".", grouping_style="western"),
    NumericCandidate(decimal_separator=".", thousand_separator=",", grouping_style="indian"),
    NumericCandidate(decimal_separator=",", thousand_separator=".", grouping_style="indian"),
)
