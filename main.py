"""
Normalization engine CLI.

Commands:
    suggest  <filename> [output_name]
    confirm  <instance_id> <config_filename> [output_name]
    profile  <instance_id> [output_name]
    convert  <instance_id> [output_name] [mode]

All input files are resolved from data/inputs/.
All outputs are written to data/outputs/<command>/.
"""

from __future__ import annotations

import sys

from app.cli.confirm import run as run_confirm
from app.cli.convert import run as run_convert
from app.cli.profile import run as run_profile
from app.cli.suggest import run as run_suggest

_COMMANDS = {
    "suggest": run_suggest,
    "confirm": run_confirm,
    "profile": run_profile,
    "convert": run_convert,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:  # noqa: PLR2004
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    _COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
