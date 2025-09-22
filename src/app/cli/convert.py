"""convert command — run normalization on a profiled instance."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from app.bootstrap.orchestrator import MainOrchestrator
from app.cli.utils import die, write_output
from shared.settings import get_settings

_USAGE = "Usage: main.py convert <instance_id>"


def run(args: list[str]) -> None:
    try:
        instance_id_str, *_ = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    try:
        instance_id = UUID(instance_id_str)
        instance = MainOrchestrator().normalize(instance_id)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        die(str(exc))
        return

    settings = get_settings()
    output_path = Path(settings.conversion_output_dir) / str(instance_id) / "instance.json"
    write_output(instance.model_dump(mode="json"), output_path)
