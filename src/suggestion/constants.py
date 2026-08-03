"""Constants shared across all suggestion inference strategies."""

from __future__ import annotations

from shared.models.operation import TraceMode

# ---------------------------------------------------------------------------
# Raw source reading
# ---------------------------------------------------------------------------

# Maximum bytes read from the file. All strategies sample from this prefix.
FILE_SAMPLE_BYTES = 4 * 1024 * 1024

# Product budget: JSON sources with roughly 1000 objects should stay within 1 GiB.
# That yields an explicit per-object budget of about 1 MiB for the first row.
JSON_FIRST_OBJECT_MAX_BYTES = 1024 * 1024

# ---------------------------------------------------------------------------
# Sample data display
# ---------------------------------------------------------------------------

# Maximum raw rows returned for display.
DISPLAY_RAW_ROWS = 15

# Maximum non-null values collected per column for type preview display.
DISPLAY_VALUES_PER_COLUMN = 10

# ---------------------------------------------------------------------------
# AI inference sampling
# ---------------------------------------------------------------------------

# Rows shown to the model when it decides a source's layout. A delimiter and a
# header row are decidable from far fewer rows than a column type is.
LAYOUT_SAMPLE_ROWS = 20

# Non-null values per column shown to the model when it types that column.
TYPING_VALUES_PER_COLUMN = 30

# ---------------------------------------------------------------------------
# Default operation config
# ---------------------------------------------------------------------------
# Pre-populate the suggested InstanceConfig after suggestion.
# The user can override any of these at confirm time.

DEFAULT_DROP_EMPTY_ROWS: bool = True
DEFAULT_FULL_RAW_ROW: bool = False
DEFAULT_INCLUDE_UNIQUE_RATIO: bool = True
DEFAULT_INCLUDE_PER_COLUMN_PARSE_ERROR_COUNTS: bool = True
DEFAULT_APPROXIMATE_UNIQUE: bool = False
DEFAULT_TRACE_MODE: TraceMode = frozenset({"issues"})
DEFAULT_DECISION_READY: float = 95.0
DEFAULT_DECISION_WARNING: float = 85.0

# An AI inference scored below this is surfaced (webhook + warning issue) in auto mode.
LOW_CONFIDENCE_THRESHOLD: float = 0.75

# ---------------------------------------------------------------------------
# Pipeline duration estimation (profile + convert)
# ---------------------------------------------------------------------------

# (row_threshold, estimated_seconds) breakpoints for linear interpolation.
# Durations are approximate — benchmark on your hardware with real data.
PIPELINE_DURATION_TIERS: tuple[tuple[int, int], ...] = (
    (10_000, 5),
    (100_000, 30),
    (1_000_000, 180),
    (10_000_000, 900),
)

# Largest single CSV field accepted, in bytes. Raises csv's 128 KB default, which is a
# guard against pathological input rather than a limit the data respects.
MAX_CSV_FIELD_BYTES = 16 * 1024 * 1024
