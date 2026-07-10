"""suggest command — run suggestion pipeline on one source file."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from shared.models.suggestion import SuggestionInput

from app.bootstrap.orchestrator import MainOrchestrator
from app.cli.utils import (
    OUTPUTS_DIR,
    default_output_name,
    die,
    infer_format_type,
    resolve_input_file,
    write_output,
)

_USAGE = "Usage: main.py suggest <filename> <extended_type_detection:true|false> [output_name]"


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("extended_type_detection must be exactly 'true' or 'false'")


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
        filename, extended_type_detection_raw, *rest = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    output_name = rest[0] if rest else default_output_name()

    try:
        input_path = resolve_input_file(filename)
        extended_type_detection = _parse_bool(extended_type_detection_raw)
        request = SuggestionInput(
            source_file=str(input_path),
            source_file_name=input_path.name,
            source_type="local",
            source_file_format=infer_format_type(input_path),
            source_checksum=_sha256_stream(input_path),
            suggestion_method="rule_based",
            extended_type_detection=extended_type_detection,
        )
        instance = MainOrchestrator().suggest(request)
    except (ValueError, FileNotFoundError) as exc:
        die(str(exc))
        return

    output_path = OUTPUTS_DIR / "suggestions" / f"{output_name}.json"
    write_output(instance.model_dump(mode="json"), output_path)
