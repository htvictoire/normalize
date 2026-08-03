"""Layout phase — produces a reading of a source under a layout that holds.

This is the one decision the rest of the pipeline waits on: until it is made
there are no columns to type, no rows to scan, and nothing to show. Formats that
declare their own layout reach a reading without a model call.

A layout is checkable against the file it claims to describe, so it is checked.
A layout that does not hold raises rather than being replaced: the caller is told
which one was tried and how it broke, and no other is attempted for them.
"""

from __future__ import annotations

from shared.errors import LayoutVerificationError
from shared.models.operation import CsvSourceFormat
from shared.models.source import SourceRef
from shared.models.suggestion import LayoutConfidence

from suggestion.ai.formats import DeclaredLayout, FormatInference, InferredLayout
from suggestion.ai.providers import FileInferenceProvider, get_inference_provider
from suggestion.source import SourceReading

# Share of data rows allowed to disagree with the column count before the layout
# is treated as wrong for the file.
MAX_DISCARDED_ROW_RATIO = 0.10

# Delimiters a one-column parse would have split on had it named the right one.
_DELIMITER_CANDIDATES = (",", ";", "\t", "|")


def resolve_layout(
    fmt: FormatInference,
    source: SourceRef,
    provider: FileInferenceProvider | None = None,
) -> tuple[SourceReading, LayoutConfidence]:
    """Resolve one source's layout, read it, and verify the read holds.

    ``provider`` is injectable for tests; production reads it from settings. It is
    never consulted for a format that declares its own layout.
    """
    if isinstance(fmt, DeclaredLayout):
        source_format = fmt.source_format()
        confidence = LayoutConfidence()
    elif isinstance(fmt, InferredLayout):
        sample = fmt.layout_sample(source)
        provider = provider or get_inference_provider()
        answer = provider.infer_schema(fmt.build_layout_prompt(sample), fmt.layout_answer)
        source_format = fmt.to_source_format(answer, source)
        confidence = fmt.layout_confidence(answer)
    else:
        raise TypeError(f"{type(fmt).__name__} neither declares nor infers a layout.")

    reading = fmt.read(source, source_format)
    try:
        _verify(reading, source.source_file_name)
    except LayoutVerificationError:
        if reading.cleanup_path is not None:
            reading.cleanup_path.unlink(missing_ok=True)
        raise
    return reading, confidence


def _verify(reading: SourceReading, source_file_name: str) -> None:
    """Raise if the resolved layout does not parse the source coherently."""
    if not reading.column_names:
        raise LayoutVerificationError(
            f"{source_file_name!r} parsed into no columns under the resolved layout."
        )
    _verify_row_alignment(reading, source_file_name)
    if isinstance(reading.source_format, CsvSourceFormat):
        _verify_delimiter_split(reading, reading.source_format.delimiter, source_file_name)


def _verify_row_alignment(reading: SourceReading, source_file_name: str) -> None:
    """Raise when too many rows disagree with the column count to trust the layout."""
    total = len(reading.inference_rows) + reading.discarded_row_count
    if not reading.discarded_row_count or not total:
        return
    ratio = reading.discarded_row_count / total
    if ratio > MAX_DISCARDED_ROW_RATIO:
        raise LayoutVerificationError(
            f"{source_file_name!r}: {reading.discarded_row_count} of {total} rows do not "
            f"have {len(reading.column_names)} fields under the resolved layout "
            f"({ratio:.0%} rejected, limit {MAX_DISCARDED_ROW_RATIO:.0%})."
        )


def _verify_delimiter_split(
    reading: SourceReading,
    delimiter: str,
    source_file_name: str,
) -> None:
    """Raise when a one-column parse leaves another delimiter sitting in the header.

    One column is legitimate only if nothing was there to split on. A header still
    holding a candidate delimiter means the resolved one does not occur in the file.
    """
    if len(reading.column_names) > 1:
        return
    header = reading.column_names[0]
    present = [
        candidate
        for candidate in _DELIMITER_CANDIDATES
        if candidate != delimiter and candidate in header
    ]
    if present:
        raise LayoutVerificationError(
            f"{source_file_name!r} parsed into a single column under delimiter "
            f"{delimiter!r}, but its header still contains "
            f"{', '.join(repr(char) for char in present)}."
        )
