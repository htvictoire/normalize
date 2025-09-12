"""JSON source helpers for suggestion Stage 1+2."""

from __future__ import annotations

import json

from shared.models.operation import JsonSourceFormat
from suggestion.constants import DISPLAY_RAW_ROWS


def infer_json_source_format() -> JsonSourceFormat:
    """Return the static JSON source format."""
    return JsonSourceFormat()


def read_json_sample_rows(sample: bytes) -> list[list[str]]:
    """
    Read sample rows from a JSON array probe.

    Only fully decoded top-level elements contained in the probe are considered.
    A partial trailing record is ignored.
    """
    decoder = json.JSONDecoder()
    text = sample.decode("utf-8-sig", errors="ignore")
    start = text.find("[")
    if start == -1:
        return []

    buf = text[start + 1 :]
    rows: list[list[str]] = []
    while len(rows) < DISPLAY_RAW_ROWS:
        buf = buf.lstrip(" \t\n\r,")
        if not buf or buf.startswith("]"):
            break
        try:
            obj, end = decoder.raw_decode(buf)
        except json.JSONDecodeError:
            break
        if not isinstance(obj, dict):
            raise TypeError("JSON files must be a top-level array of objects.")
        rows.append([str(value) if value is not None else "" for value in obj.values()])
        buf = buf[end:]
    return rows
