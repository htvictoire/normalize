"""CLI runner for manual end-to-end pipeline execution.

Usage: python runner.py [csv_path] [mode] [trace_mode]

Arguments:
    csv_path    — path to input CSV (default: data/prod_like_10m.csv)
    mode        — PROFILE or APPLY (default: APPLY)
    trace_mode  — full or sparse (default: sparse)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from normalize.core.engine import EngineConfig, NormalizationEngine
from normalize.stages.ingestion.contracts import HeaderMode


def main() -> None:
    """Run the configured pipeline and print structured JSON result."""
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/prod_like_10m.csv"
    mode = sys.argv[2] if len(sys.argv) > 2 else "APPLY"
    trace_mode = sys.argv[3] if len(sys.argv) > 3 else "sparse"

    now_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    config = EngineConfig(
        rules_version="v1",
        duckdb_path=f"data/manual_runs/{now_prefix}_{mode.lower()}.duckdb",
        threads=8,
        header_mode=HeaderMode.PRESENT,
        header_row_index=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        thousand_separator=",",
        allow_leading_decimal_point=True,
        date_formats={},
        null_tokens=("", "null", "none", "n/a", "-"),
        boolean_true_tokens=("true", "yes", "1"),
        boolean_false_tokens=("false", "no", "0"),
        type_inference_numeric_threshold=0.95,
        type_inference_boolean_threshold=0.95,
        assign_indices=True,
        drop_empty_rows=True,
        emit_raw_row=True,
        full_raw_row=False,
        emit_parse_issues=True,
        include_unique_ratio=True,
        include_per_column_parse_error_counts=True,
        approximate_unique=True,
        decision_ready_threshold=95.0,
        decision_warning_threshold=85.0,
        trace_mode=trace_mode,
    )

    start = perf_counter()
    result = NormalizationEngine().run(
        csv_path=Path(csv_path),
        output_dir=Path("data/manual_runs"),
        config=config,
        mode=mode,
    )
    result["wall_seconds"] = perf_counter() - start
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
