"""Raw CSV decoding: encoding detection and mechanical row extraction.

Delimiter and header-row detection are heuristic guesses, not mechanical
decoding, and live in suggestion.rule_based.source.csv instead — this module
only knows how to decode bytes and slice rows once those parameters are
already resolved (by whichever inference strategy resolved them).
"""

from __future__ import annotations

import csv

from suggestion.constants import DISPLAY_RAW_ROWS, MAX_CSV_FIELD_BYTES

# csv defaults to a 128 KB field limit and raises csv.Error beyond it. A large cell is
# legal data, not a malformed file, so the limit is raised here, at the single module
# that decodes CSV text. Every csv.reader in the suggestion layer runs after this import.
csv.field_size_limit(MAX_CSV_FIELD_BYTES)


def infer_csv_encoding(sample: bytes) -> str:
    """Detect text encoding from a byte sample via BOM sniffing with a safe fallback."""
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return "latin-1"
    return "utf-8"


def read_csv_column_names_and_inference_rows(
    text: str,
    delimiter: str,
    header_mode: str,
    header_row_index: int | None,
) -> tuple[list[str], list[list[str]], int]:
    """Parse column names, data rows, and the count of rows rejected as ragged.

    A row whose field count differs from the header's cannot be positioned, so it
    is excluded from inference and counted rather than dropped in silence.
    """
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        return [], [], 0

    first_non_empty_row = next((row for row in rows if row), rows[0])
    col_count = len(first_non_empty_row)

    if header_mode == "present" and header_row_index is not None:
        header_idx = header_row_index - 1
        if header_idx < len(rows):
            column_names = [cell.strip() or f"col_{i}" for i, cell in enumerate(rows[header_idx])]
            col_count = len(column_names)
        else:
            column_names = [f"col_{i}" for i in range(col_count)]
        data_start = header_idx + 1
    else:
        column_names = [f"col_{i}" for i in range(col_count)]
        data_start = 0

    data_rows = rows[data_start:]
    inference_rows = [row for row in data_rows if len(row) == col_count]
    return column_names, inference_rows, len(data_rows) - len(inference_rows)


def read_csv_sample_rows(text: str, delimiter: str) -> list[list[str]]:
    """Return the first DISPLAY_RAW_ROWS rows from decoded CSV text as raw string lists."""
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for i, row in enumerate(reader):
        if i >= DISPLAY_RAW_ROWS:
            break
        rows.append(row)
    return rows
