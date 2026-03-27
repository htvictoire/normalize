"""JSON source helpers for suggestion Stage 1+2."""

from __future__ import annotations

import json
from collections.abc import Iterator

from shared.models.operation import JsonSourceFormat

from suggestion.constants import DISPLAY_RAW_ROWS


def infer_json_source_format() -> JsonSourceFormat:
    """Return the static JSON source format."""
    return JsonSourceFormat()


def _iter_json_array_objects(
    sample: bytes,
    *,
    require_first_object: bool = False,
) -> Iterator[dict[str, object]]:
    decoder = json.JSONDecoder()
    text = sample.decode("utf-8-sig", errors="ignore")
    start = text.find("[")
    if start == -1:
        raise ValueError("JSON files must be a top-level array of objects.")

    buf = text[start + 1 :]
    yielded_any = False
    while True:
        buf = buf.lstrip(" \t\n\r,")
        if not buf or buf.startswith("]"):
            return
        try:
            obj, end = decoder.raw_decode(buf)
        except json.JSONDecodeError as exc:
            if require_first_object and not yielded_any:
                raise ValueError(
                    "The first JSON object exceeds the configured size budget or is malformed."
                ) from exc
            return
        if not isinstance(obj, dict):
            raise TypeError("JSON files must be a top-level array of objects.")
        yielded_any = True
        yield obj
        buf = buf[end:]


def ensure_json_first_object_within_limit(sample: bytes) -> None:
    """Fail fast if the first JSON object does not fit inside the configured byte budget."""
    next(_iter_json_array_objects(sample, require_first_object=True), None)


def _ordered_json_row(obj: dict[str, object], column_names: list[str]) -> list[str]:
    if set(obj.keys()) != set(column_names):
        raise ValueError("JSON files must contain objects with a consistent key set.")
    return [str(obj[name]) if obj[name] is not None else "" for name in column_names]


def read_json_column_names_and_inference_rows(
    sample: bytes,
) -> tuple[list[str], list[list[str]]]:
    """Parse column names and all data rows from a JSON array byte probe."""
    column_names: list[str] = []
    rows: list[list[str]] = []

    for obj in _iter_json_array_objects(sample):
        if not column_names:
            column_names = list(obj.keys())
        rows.append(_ordered_json_row(obj, column_names))

    return column_names, rows


def read_json_sample_rows(sample: bytes) -> list[list[str]]:
    """Read up to DISPLAY_RAW_ROWS rows from a JSON array probe using stable key order."""
    column_names: list[str] | None = None
    rows: list[list[str]] = []
    for obj in _iter_json_array_objects(sample):
        if column_names is None:
            column_names = list(obj.keys())
        rows.append(_ordered_json_row(obj, column_names))
        if len(rows) >= DISPLAY_RAW_ROWS:
            break
    return rows
