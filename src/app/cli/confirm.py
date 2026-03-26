"""confirm command — submit a confirmed config for an existing instance."""

from __future__ import annotations

import json
import sys
from uuid import UUID

from app.bootstrap.orchestrator import MainOrchestrator
from app.cli.utils import (
    OUTPUTS_DIR,
    default_output_name,
    die,
    resolve_input_file,
    write_output,
)
from shared.models.instance import InstanceConfig

_USAGE = "Usage: main.py confirm <instance_id> <config_filename> [output_name]"


def run(args: list[str]) -> None:
    try:
        instance_id_str, config_filename, *rest = args
    except ValueError:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)

    output_name = rest[0] if rest else default_output_name()

    try:
        instance_id = UUID(instance_id_str)
        config_path = resolve_input_file(config_filename)
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        confirmed_config = InstanceConfig.model_validate(raw)
        instance = MainOrchestrator().confirm(instance_id, confirmed_config)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        die(str(exc))
        return

    output_path = OUTPUTS_DIR / "confirmations" / f"{output_name}.json"
    write_output(instance.model_dump(mode="json"), output_path)
