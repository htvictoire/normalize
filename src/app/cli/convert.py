"""convert command — run normalization on a profiled instance."""

from __future__ import annotations

import sys
from uuid import UUID

from app.bootstrap.orchestrator import MainOrchestrator
from app.cli.utils import (
    OUTPUTS_DIR,
    VALID_MODES,
    default_output_name,
    die,
    write_output,
)

_USAGE = "Usage: main.py convert <instance_id> [output_name] [mode]"


def run(args: list[str]) -> None:
    try:
        instance_id_str, *rest = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    output_name = rest[0] if rest else default_output_name()
    mode = rest[1] if len(rest) > 1 else "APPLY"

    if mode not in VALID_MODES:
        die(f"Invalid mode {mode!r}. Must be one of: {sorted(VALID_MODES)}")
        return

    output_dir = OUTPUTS_DIR / "conversions" / output_name

    try:
        instance_id = UUID(instance_id_str)
        instance = MainOrchestrator().normalize(
            instance_id,
            output_dir=output_dir,
            mode=mode,  # type: ignore[arg-type]
        )
    except (ValueError, FileNotFoundError, KeyError) as exc:
        die(str(exc))
        return

    output_path = output_dir / "instance.json"
    write_output(instance.model_dump(mode="json"), output_path)
