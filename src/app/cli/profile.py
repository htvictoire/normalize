"""profile command — run full-dataset profiling on a confirmed instance."""

from __future__ import annotations

import sys
from uuid import UUID

from app.bootstrap.orchestrator import MainOrchestrator
from app.cli.utils import (
    OUTPUTS_DIR,
    default_output_name,
    die,
    write_output,
)

_USAGE = "Usage: main.py profile <instance_id> [output_name]"


def run(args: list[str]) -> None:
    try:
        instance_id_str, *rest = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    output_name = rest[0] if rest else default_output_name()

    try:
        instance_id = UUID(instance_id_str)
        instance = MainOrchestrator().profile(instance_id)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        die(str(exc))
        return

    output_path = OUTPUTS_DIR / "profiles" / f"{output_name}.json"
    write_output(instance.model_dump(mode="json"), output_path)
