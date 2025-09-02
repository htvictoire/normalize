"""Infer CsvSourceFormat from raw file bytes."""

from __future__ import annotations

import csv
from collections import Counter

from shared.models.operation import CsvSourceFormat
from suggestion.constants import (
    DELIMITER_CANDIDATES,
    HEADER_SCAN_ROWS,
    HEADER_SCORE_LOOKAHEAD,
)


def _looks_numeric(value: str) -> bool:
    """Return True when digits make up at least half the characters of value."""
    stripped = value.strip()
    if not stripped:
        return False
    digits = sum(1 for char in stripped if char.isdigit())
    return digits > 0 and digits >= max(len(stripped) // 2, 1)


def _read_rows(text: str, *, delimiter: str, limit: int) -> list[list[str]]:
    """Read up to limit rows from text using the given delimiter."""
    rows: list[list[str]] = []
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    for index, row in enumerate(reader):
        if index >= limit:
            break
        rows.append(row)
    return rows


def _scan_for_header_row(text: str, delimiter: str) -> int | None:
    rows = _read_rows(text, delimiter=delimiter, limit=HEADER_SCAN_ROWS)
    if not rows:
        return None

    col_counts = [len(row) for row in rows]
    modal_count = max(set(col_counts), key=col_counts.count)
    if modal_count == 0:
        return None

    eligible_indices = [i for i, row in enumerate(rows) if len(row) == modal_count]

    candidates: list[tuple[int, list[str]]] = []
    for i in eligible_indices:
        values = [v.strip() for v in rows[i]]
        if any(values) and len(set(values)) == len(values):
            candidates.append((i, values))

    if not candidates:
        return None

    best_row_index: int | None = None
    best_score: float = float("-inf")

    for orig_index, values in candidates:
        numeric_count = sum(1 for v in values if _looks_numeric(v))

        subsequent = [
            idx for idx in eligible_indices if idx > orig_index
        ][:HEADER_SCORE_LOOKAHEAD]

        if subsequent:
            subsequent_numeric_avg = sum(
                sum(1 for v in [c.strip() for c in rows[idx]] if _looks_numeric(v))
                for idx in subsequent
            ) / len(subsequent)
            score: float = subsequent_numeric_avg - numeric_count
        else:
            score = float(-numeric_count)

        if score > best_score:
            best_score = score
            best_row_index = orig_index

    if best_row_index is not None and best_score > 0:
        return best_row_index + 1

    return None


def _detect_header_row(text: str, delimiter: str) -> int | None:
    """
    Return the 1-based index of the header row, or None if no header is found.

    Pass 1 -- csv.Sniffer on the first 128 KB. Returns 1 immediately when
              Sniffer confirms a header without raising.

    Pass 2 -- full scan up to HEADER_SCAN_ROWS rows. Used when Sniffer
              returns False or fails, which happens when the header is not
              at row 0 (preamble rows, blank separators, or data rows before
              the header).

              For each candidate row (correct column count, all-unique
              non-empty values), compute:

                score = avg_numeric(subsequent rows) - numeric_count(candidate)

              The header row has near-zero numeric density while data rows
              have higher numeric density, so the header scores highest.
              When no subsequent rows are available, score = -numeric_count.

              A candidate is accepted only when its score is strictly
              positive. Returns None otherwise.
    """
    snippet = text[:128_000]
    if not snippet.strip():
        return 1

    try:
        if csv.Sniffer().has_header(snippet):
            return 1
    except csv.Error:
        pass

    return _scan_for_header_row(text, delimiter)


def _infer_encoding(sample: bytes) -> str:
    """
    Detect encoding from BOM markers, falling back to UTF-8 probe then latin-1.

    Rules applied in order:
      utf-8-sig  -- BOM EF BB BF (Excel UTF-8 export)
      utf-16     -- BOM FF FE or FE FF
      utf-8      -- sample decodes as UTF-8 without error
      latin-1    -- fallback; accepts every byte value without raising
    """
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
    """
    Detect the field delimiter from the first 128 KB of text.

    Pass 1 -- csv.Sniffer on the first 128 KB.
    Pass 2 -- fallback scoring across the first 20 non-empty lines.
              Each candidate is scored as modal_count * lines_matching_modal_count,
              where modal_count is the most common per-line occurrence count.
              A true delimiter appears the same number of times in every row.
    Default -- comma when the file is empty or no candidate scores above zero.
    """
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
    """Infer all CsvSourceFormat fields from an already-read byte sample."""
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
