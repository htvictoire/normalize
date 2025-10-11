"""Sign marker constants and detection helpers."""

from __future__ import annotations

import re

NEGATIVE_SIGN_MARKERS: frozenset[str] = frozenset({"CR", "-"})
POSITIVE_SIGN_MARKERS: frozenset[str] = frozenset({"DR", "+"})
KNOWN_SIGN_MARKERS: tuple[str, ...] = tuple(sorted(NEGATIVE_SIGN_MARKERS | POSITIVE_SIGN_MARKERS))


def _sign_marker_detection_pattern() -> str:
    escaped = sorted(
        (re.escape(t.lower()) for t in KNOWN_SIGN_MARKERS), key=len, reverse=True
    )
    return r"(?<=[0-9])\s*(" + "|".join(escaped) + r")\s*$"


SIGN_MARKER_DETECTION_RE = re.compile(_sign_marker_detection_pattern(), re.IGNORECASE)
