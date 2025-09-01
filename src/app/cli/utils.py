"""Shared utilities for manage.py CLI commands."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import get_args

from shared.models.operation import FileFormat, RunMode

VALID_MODES: frozenset[str] = frozenset(get_args(RunMode))

_FORMAT_BY_EXTENSION: dict[str, FileFormat] = {
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
}

INPUTS_DIR = Path("data/inputs")
OUTPUTS_DIR = Path("data/outputs")


def default_output_name() -> str:
    """Return a datetime-based output name (e.g. 2026-03-19T14-30-00)."""
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def resolve_input_file(filename: str) -> Path:
    """Resolve a bare filename to data/inputs/<filename> and validate it exists."""
    path = INPUTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return path


def infer_format_type(path: Path) -> FileFormat:
    """Infer FileFormat from the file extension."""
    ext = path.suffix.lower()
    fmt = _FORMAT_BY_EXTENSION.get(ext)
    if fmt is None:
        raise ValueError(
            f"Cannot infer format from extension {ext!r}. "
            "Supported: .csv, .xlsx, .xls, .json"
        )
    return fmt


def write_output(data: object, output_path: Path) -> None:
    """Write data as formatted JSON to output_path and print to stdout."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=True, sort_keys=True, default=str) + "\n"
    output_path.write_text(text, encoding="utf-8")
    print(text, end="")


def die(message: str) -> None:
    """Print error to stderr and exit with code 1."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)
