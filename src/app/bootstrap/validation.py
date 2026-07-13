"""Input validation for the normalization lifecycle."""

from __future__ import annotations

from pathlib import Path

from shared.errors import InvalidRequestError, SourceError
from shared.models.operation import FileFormat
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionInput
from shared.storage.probe import read_source_probe

_VALID_EXTENSION: dict[FileFormat, str] = {
    "csv": ".csv",
    "excel": ".xlsx",
    "json": ".json",
}

_VALIDATION_PROBE_BYTES = 8 * 1024
_XLSX_MAGIC = b"PK\x03\x04"
_UTF8_BOM = b"\xef\xbb\xbf"


def _json_probe_payload(probe: bytes) -> bytes:
    if probe.startswith(_UTF8_BOM):
        probe = probe[len(_UTF8_BOM) :]
    return probe.lstrip()


def validate_auto_confirm(request: SuggestionInput) -> None:
    """Reject auto-confirmation of a rule-based config.

    Auto mode converts without a human reading the config. The rule-based strategy
    reports a fixed confidence and cannot signal a column it failed to type, so a
    defeated inference is indistinguishable from a successful one. Only a strategy
    that scores its own guesses may be confirmed unattended.
    """
    if request.auto_confirm and request.suggestion_method == "rule_based":
        raise InvalidRequestError(
            "auto_confirm requires suggestion_method='ai'. The rule-based strategy does "
            "not score its inferences and must be confirmed before conversion."
        )


def validate_file_format(source: SourceRef) -> None:
    """
    Validate that the file extension and magic bytes both match the declared format.

    Raises SourceError on any mismatch so the caller surfaces an error immediately.
    Validation is strict — ambiguity is an error, not a warning.

    JSON files must be a top-level array (first non-whitespace byte is '[').
    Single-object and newline-delimited JSON are rejected for determinism.
    """
    ext = Path(source.source_file_name).suffix.lower()
    if ext != _VALID_EXTENSION[source.source_file_format]:
        raise SourceError(
            f"Extension {ext!r} is not valid for format {source.source_file_format!r}. "
            f"Expected {_VALID_EXTENSION[source.source_file_format]!r}."
        )

    probe = read_source_probe(source, _VALIDATION_PROBE_BYTES)
    is_xlsx = probe.startswith(_XLSX_MAGIC)

    if source.source_file_format == "excel" and not is_xlsx:
        raise SourceError(
            "Declared format is 'excel' but file does not have XLSX magic bytes."
        )
    if source.source_file_format != "excel" and is_xlsx:
        raise SourceError(
            f"File has Excel magic bytes but declared format is {source.source_file_format!r}."
        )

    if source.source_file_format == "json":
        stripped = _json_probe_payload(probe)
        if not stripped or stripped[0:1] != b"[":
            raise SourceError(
                "JSON files must be a top-level array starting with '['. "
                "Single-object and newline-delimited JSON are not supported."
            )
