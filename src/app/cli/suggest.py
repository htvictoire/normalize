"""suggest command — run suggestion pipeline on one source file."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from shared.models.source import SourceRef

from app.bootstrap.orchestrator import MainOrchestrator
from app.cli.utils import (
    OUTPUTS_DIR,
    default_output_name,
    die,
    infer_format_type,
    resolve_input_file,
    write_output,
)

_USAGE = "Usage: main.py suggest <filename> [output_name]"


def _sha256_stream(path: Path, chunk_size: int = 1_048_576) -> str:
    """Compute SHA256 of a local file using chunked reads."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def run(args: list[str]) -> None:
    try:
        filename, *rest = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    output_name = rest[0] if rest else default_output_name()

    try:
        input_path = resolve_input_file(filename)
        source = SourceRef(
            source_file=str(input_path),
            source_file_name=input_path.name,
            source_type="local",
            source_file_format=infer_format_type(input_path),
        )
        instance = MainOrchestrator().suggest(
            source,
            _sha256_stream(input_path),
            "rule_based",
        )
    except (ValueError, FileNotFoundError) as exc:
        die(str(exc))
        return

    output_path = OUTPUTS_DIR / "suggestions" / f"{output_name}.json"
    write_output(instance.model_dump(mode="json"), output_path)
