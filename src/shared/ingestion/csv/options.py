"""Strict CSV option validation and translation for DuckDB loaders."""

from __future__ import annotations

from shared.ingestion.contracts import HeaderMode

SUPPORTED_ENCODINGS = {"utf-8", "utf-8-sig", "latin-1", "utf-16"}


def resolve_header_options(
    header_mode: HeaderMode,
    header_row_index: int | None,
) -> tuple[bool, int]:
    """
    Validate explicit header config and map it to DuckDB CSV options.

    Returns:
    - `header`: value for DuckDB `header` option
    - `skip`: value for DuckDB `skip` option

    Error codes surfaced via `ValueError` message:
    - `MISSING_HEADER_ROW_INDEX`
    - `INVALID_HEADER_ROW_INDEX`
    - `HEADER_ROW_INDEX_NOT_ALLOWED`
    """
    if header_mode is HeaderMode.PRESENT:
        if header_row_index is None:
            raise ValueError("MISSING_HEADER_ROW_INDEX")
        if header_row_index < 1:
            raise ValueError("INVALID_HEADER_ROW_INDEX")
        return (True, header_row_index - 1)

    if header_row_index is not None:
        raise ValueError("HEADER_ROW_INDEX_NOT_ALLOWED")
    return (False, 0)


def resolve_encoding_option(encoding: str) -> tuple[str, str]:
    """
    Validate configured encoding and map to DuckDB-compatible encoding.

    Returns:
    - `display_encoding`: encoding reported in metadata
    - `duckdb_encoding`: encoding value used by DuckDB CSV loader

    Error codes surfaced via `ValueError` message:
    - `MISSING_ENCODING`
    - `UNSUPPORTED_ENCODING`
    """
    normalized = encoding.strip().lower()
    if not normalized:
        raise ValueError("MISSING_ENCODING")
    if normalized not in SUPPORTED_ENCODINGS:
        raise ValueError("UNSUPPORTED_ENCODING")
    if normalized == "utf-8-sig":
        return ("utf-8-sig", "utf-8")
    return (normalized, normalized)


def resolve_delimiter_option(delimiter: str) -> str:
    """
    Validate configured delimiter.

    Rules:
    - delimiter is required
    - exactly one character

    Error codes surfaced via `ValueError` message:
    - `MISSING_DELIMITER`
    - `INVALID_DELIMITER`
    """
    if not delimiter:
        raise ValueError("MISSING_DELIMITER")
    if len(delimiter) != 1:
        raise ValueError("INVALID_DELIMITER")
    return delimiter
