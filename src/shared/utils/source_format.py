"""Infer source-format settings directly from CSV file content."""

from __future__ import annotations

import csv
from pathlib import Path

from shared.models.operation import SourceFormatConfig

_SNIFFER_DELIMITERS = [",", ";", "\t", "|"]
_HEADER_COMPARISON_ROWS = 2


def infer_source_format(
    file_path: Path,
    *,
    sample_bytes: int = 4 * 1024 * 1024,
) -> SourceFormatConfig:
    """Infer source-format fields from file bytes."""
    sample = file_path.read_bytes()[:sample_bytes]
    encoding = _infer_encoding(sample)
    text = sample.decode(encoding, errors="ignore")
    delimiter = _infer_delimiter(text)
    header_present = _infer_header_presence(text, delimiter)
    return SourceFormatConfig(
        encoding=encoding,
        delimiter=delimiter,
        header_mode="present" if header_present else "absent",
        header_row_index=1 if header_present else None,
    )


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
        dialect = csv.Sniffer().sniff(snippet, delimiters="".join(_SNIFFER_DELIMITERS))
        if dialect.delimiter in _SNIFFER_DELIMITERS:
            return dialect.delimiter
    except csv.Error:
        pass

    lines = [line for line in snippet.splitlines()[:20] if line]
    if not lines:
        return ","
    scores = dict.fromkeys(_SNIFFER_DELIMITERS, 0)
    for line in lines:
        for delimiter in _SNIFFER_DELIMITERS:
            scores[delimiter] += line.count(delimiter)
    return max(scores.items(), key=lambda item: item[1])[0]


def _infer_header_presence(text: str, delimiter: str) -> bool:
    snippet = text[:128_000]
    if not snippet.strip():
        return True
    try:
        dialect = csv.excel()
        dialect.delimiter = delimiter
        has_header = csv.Sniffer().has_header(snippet)
        return bool(has_header)
    except csv.Error:
        pass

    rows = _read_rows(snippet, delimiter=delimiter, limit=_HEADER_COMPARISON_ROWS)
    if len(rows) < _HEADER_COMPARISON_ROWS:
        return True
    first, second = rows[0], rows[1]
    first_numeric = sum(1 for value in first if _looks_numeric(value))
    second_numeric = sum(1 for value in second if _looks_numeric(value))
    return first_numeric < second_numeric


def _read_rows(text: str, *, delimiter: str, limit: int) -> list[list[str]]:
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for index, row in enumerate(reader):
        if index >= limit:
            break
        rows.append(row)
    return rows


def _looks_numeric(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    digits = sum(1 for char in stripped if char.isdigit())
    return digits > 0 and digits >= max(len(stripped) // 2, 1)
