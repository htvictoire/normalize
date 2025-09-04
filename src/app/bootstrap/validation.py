"""Input validation for the normalization lifecycle."""

from __future__ import annotations

from pathlib import Path

from shared.models.operation import FileFormat

_VALID_EXTENSIONS: dict[FileFormat, frozenset[str]] = {
    "csv": frozenset({".csv"}),
    "excel": frozenset({".xlsx", ".xls"}),
    "json": frozenset({".json"}),
}

_EXCEL_MAGIC = (
    b"PK\x03\x04",          # XLSX (ZIP)
    b"\xd0\xcf\x11\xe0",    # XLS (OLE2)
)


def validate_file_format(file_path: Path, declared_format: FileFormat) -> None:
    """
    Validate that the file extension and magic bytes both match the declared format.

    Raises ValueError on any mismatch so the caller surfaces an error immediately.
    Validation is strict — ambiguity is an error, not a warning.

    JSON files must be a top-level array (first non-whitespace byte is '[').
    Single-object and newline-delimited JSON are rejected for determinism.
    """
    ext = file_path.suffix.lower()
    if ext not in _VALID_EXTENSIONS[declared_format]:
        allowed = sorted(_VALID_EXTENSIONS[declared_format])
        raise ValueError(
            f"Extension {ext!r} is not valid for format {declared_format!r}. "
            f"Expected one of: {allowed}"
        )

    with file_path.open("rb") as fh:
        magic = fh.read(8)

    is_excel = any(magic.startswith(sig) for sig in _EXCEL_MAGIC)

    if declared_format == "excel" and not is_excel:
        raise ValueError(
            "Declared format is 'excel' but file does not have Excel magic bytes."
        )
    if declared_format != "excel" and is_excel:
        raise ValueError(
            f"File has Excel magic bytes but declared format is {declared_format!r}."
        )

    if declared_format == "json":
        stripped = magic.lstrip()
        if not stripped or stripped[0:1] != b"[":
            raise ValueError(
                "JSON files must be a top-level array starting with '['. "
                "Single-object and newline-delimited JSON are not supported."
            )
