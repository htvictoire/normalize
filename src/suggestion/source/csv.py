"""Infer CsvSourceFormat from raw file bytes."""

from __future__ import annotations

import csv
from collections import Counter

from shared.models.operation import CsvSourceFormat

from suggestion.constants import (
    DELIMITER_CANDIDATES,
    DISPLAY_RAW_ROWS,
    HEADER_SCAN_ROWS,
    HEADER_SCORE_LOOKAHEAD,
)
from suggestion.source.heuristics import looks_numeric


def _read_rows(text: str, delimiter: str, limit: int) -> list[list[str]]:
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for index, row in enumerate(reader):
        if index >= limit:
            break
        rows.append(row)
    return rows


def _scan_for_header_row(text: str, delimiter: str) -> int | None:
    rows = _read_rows(text, delimiter, HEADER_SCAN_ROWS)
    if not rows:
        return None

    col_counts = [len(row) for row in rows]
    modal_count = max(Counter(col_counts).items(), key=lambda item: (item[1], item[0]))[0]
    if modal_count == 0:
        return None

    eligible_indices = [i for i, row in enumerate(rows) if len(row) == modal_count]

    candidates: list[tuple[int, list[str]]] = []
    for index in eligible_indices:
        values = [value.strip() for value in rows[index]]
        if any(values):
            candidates.append((index, values))

    if not candidates:
        return None

    best_row_index: int | None = None
    best_score = float("-inf")
    for original_index, values in candidates:
        numeric_count = sum(1 for value in values if looks_numeric(value))
        subsequent = [idx for idx in eligible_indices if idx > original_index][
            :HEADER_SCORE_LOOKAHEAD
        ]

        if subsequent:
            subsequent_numeric_avg = sum(
                sum(1 for value in [cell.strip() for cell in rows[idx]] if looks_numeric(value))
                for idx in subsequent
            ) / len(subsequent)
            score = subsequent_numeric_avg - numeric_count
        else:
            score = float(-numeric_count)

        if score > best_score:
            best_score = score
            best_row_index = original_index

    if best_row_index is not None and best_score > 0:
        return best_row_index + 1
    return None


def _detect_header_row(text: str, delimiter: str) -> int | None:
    snippet = text[:128_000]
    if not snippet.strip():
        return None

    try:
        if csv.Sniffer().has_header(snippet):
            return 1
    except csv.Error:
        pass

    return _scan_for_header_row(text, delimiter)


def _infer_encoding(sample: bytes) -> str:
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return "latin-1"
    return "utf-8"


def _infer_delimiter(text: str) -> str:
    snippet = text[:128_000]
    if not snippet.strip():
        return ","

    try:
        dialect = csv.Sniffer().sniff(snippet, delimiters="".join(DELIMITER_CANDIDATES))
        if dialect.delimiter in DELIMITER_CANDIDATES:
            return dialect.delimiter
    except csv.Error:
        pass

    lines = [line for line in snippet.splitlines()[:20] if line]
    if not lines:
        return ","

    best_delimiter = ","
    best_score = -1
    for candidate in DELIMITER_CANDIDATES:
        counts = [line.count(candidate) for line in lines]
        if not any(counts):
            continue
        mode_count, mode_freq = Counter(counts).most_common(1)[0]
        if mode_count == 0:
            continue
        score = mode_count * mode_freq
        if score > best_score:
            best_score = score
            best_delimiter = candidate
    return best_delimiter


def read_csv_column_names_and_inference_rows(
    text: str,
    delimiter: str,
    header_mode: str,
    header_row_index: int | None,
) -> tuple[list[str], list[list[str]]]:
    """Parse column names and all data rows from decoded CSV text."""
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        return [], []

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

    return column_names, [row for row in rows[data_start:] if len(row) == col_count]


def read_csv_sample_rows(text: str, delimiter: str) -> list[list[str]]:
    """Return the first DISPLAY_RAW_ROWS rows from decoded CSV text as raw string lists."""
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for i, row in enumerate(reader):
        if i >= DISPLAY_RAW_ROWS:
            break
        rows.append(row)
    return rows


def infer_csv_source_format(sample: bytes) -> CsvSourceFormat:
    """Infer CSV format settings from a pre-read byte sample."""
    encoding = _infer_encoding(sample)
    text = sample.decode(encoding, errors="ignore")
    delimiter = _infer_delimiter(text)
    header_row_index = _detect_header_row(text, delimiter)
    return CsvSourceFormat(
        encoding=encoding,
        delimiter=delimiter,
        header_mode="present" if header_row_index is not None else "absent",
        header_row_index=header_row_index,
    )
