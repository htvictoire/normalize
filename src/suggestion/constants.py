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
# Default operation config
# ---------------------------------------------------------------------------
# Pre-populate the suggested InstanceConfig after suggestion.
# The user can override any of these at confirm time.

DEFAULT_ASSIGN_INDICES: bool = False
DEFAULT_DROP_EMPTY_ROWS: bool = True
DEFAULT_FULL_RAW_ROW: bool = False
DEFAULT_INCLUDE_UNIQUE_RATIO: bool = True
DEFAULT_INCLUDE_PER_COLUMN_PARSE_ERROR_COUNTS: bool = True
DEFAULT_APPROXIMATE_UNIQUE: bool = False
DEFAULT_TRACE_MODE: TraceMode = "sparse"
DEFAULT_DECISION_READY: float = 95.0
DEFAULT_DECISION_WARNING: float = 85.0

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
