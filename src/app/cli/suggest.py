"""suggest command — run suggestion pipeline on one source file."""

from __future__ import annotations

import sys

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


def run(args: list[str]) -> None:
    try:
        filename, *rest = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    output_name = rest[0] if rest else default_output_name()

    try:
        input_path = resolve_input_file(filename)
        format_type = infer_format_type(input_path)
        instance = MainOrchestrator().suggest(
            file_path=input_path,
            source_file_name=input_path.name,
            format_type=format_type,
        )
    except (ValueError, FileNotFoundError) as exc:
        die(str(exc))
        return

    output_path = OUTPUTS_DIR / "suggestions" / f"{output_name}.json"
    write_output(instance.model_dump(mode="json"), output_path)
