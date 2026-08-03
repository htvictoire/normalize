"""Input validation for the normalization lifecycle."""

from __future__ import annotations

from pathlib import Path

from shared.errors import SourceError
from shared.models.operation import FileFormat
from shared.models.source import SourceRef
from shared.settings import get_settings
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


def validate_source_path(source: SourceRef) -> None:
    """Reject a local source that resolves outside the permitted root.

    ``resolve()`` follows symlinks and collapses ``..``, so containment is checked
    against the real target. S3 sources are not path-checked. Callers only reach
    this once a real source_file exists (never for a draft's sample alone).
    """
    if source.source_type != "local":
        return
    if source.source_file is None:
        raise SourceError("Source has no source_file to validate.")
    root = Path(get_settings().local_source_root).resolve()
    resolved = Path(source.source_file).resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise SourceError("Source file is outside the permitted directory.")


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
