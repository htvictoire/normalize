"""Tunables for the AI inference strategy."""

from __future__ import annotations

# Number of whole rows (header + data) sampled and sent to the model. Kept as
# a full row set rather than per-column values so the model retains
# cross-column context (e.g. a currency column next to an amount column).
DEFAULT_SAMPLE_ROW_COUNT = 50
