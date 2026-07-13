"""Heuristic CSV format inference: delimiter and header-row detection.

This is a guess, not mechanical decoding — it is one strategy's way of
resolving a CsvSourceFormat from raw bytes. Mechanical decoding once the
format is known lives in suggestion.source.csv.
"""

from __future__ import annotations

import csv
from collections import Counter

from shared.models.operation import CsvSourceFormat

from suggestion.rule_based.constants import DELIMITER_CANDIDATES, HEADER_SCAN_ROWS
from suggestion.rule_based.source.heuristics import is_header_like
from suggestion.source.csv import infer_csv_encoding


def _read_rows(text: str, delimiter: str, limit: int) -> list[list[str]]:
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for index, row in enumerate(reader):
        if index >= limit:
            break
        rows.append(row)
    return rows


def _scan_for_header_row(text: str, delimiter: str) -> int | None:
    """Return the 1-based header row, or None when the file has no header.

    The topmost header-shaped row of the table's dominant width wins. Rows above it
    are preamble and are skipped at ingestion.

    None is a valid result, not a failure: a file whose rows all carry data has no
    header, and reporting one would consume its first row as labels.
    """
    rows = _read_rows(text, delimiter, HEADER_SCAN_ROWS)
    if not rows:
        return None

    col_counts = [len(row) for row in rows]
    modal_count = max(Counter(col_counts).items(), key=lambda item: (item[1], item[0]))[0]
    if modal_count == 0:
        return None

    for index, row in enumerate(rows):
        if len(row) == modal_count and is_header_like(list(row)):
            return index + 1
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

    try:
        return _scan_for_header_row(text, delimiter)
    except csv.Error:
        # A field wider than csv's field-size limit leaves no row readable, so there is
        # no evidence of a header. Reporting none costs one misread row; raising would
        # abort suggestion entirely.
        return None


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


def infer_csv_source_format(sample: bytes) -> CsvSourceFormat:
    """Infer CSV format settings from a pre-read byte sample."""
    encoding = infer_csv_encoding(sample)
    text = sample.decode(encoding, errors="ignore")
    delimiter = _infer_delimiter(text)
    header_row_index = _detect_header_row(text, delimiter)
    return CsvSourceFormat(
        encoding=encoding,
        delimiter=delimiter,
        header_mode="present" if header_row_index is not None else "absent",
        header_row_index=header_row_index,
    )
