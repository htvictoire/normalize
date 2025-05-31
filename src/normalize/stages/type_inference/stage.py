"""Basic type inference stage."""

from __future__ import annotations

from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.token_policy import TokenPolicy
from normalize.stages.base import Stage
from normalize.stages.shared_profiling import (
    DEFAULT_PROFILE_TABLE_NAME,
    ensure_column_profiles,
)
from normalize.stages.type_inference.inference import infer_column_type


class TypeInferenceStage(Stage):
    """
    Infer column types from parse-success ratios.

    Rules:
    - Boolean threshold is configurable and required per run.
    - Integer/float threshold is configurable and required per run.
    - Priority: boolean -> integer -> float -> string.
    - Empty columns infer to string.

    Token policy inputs are mandatory and validated on every call:
    - `null_tokens`
    - `boolean_true_tokens`
    - `boolean_false_tokens`
    """

    def __init__(
        self,
        *,
        numeric_threshold: float,
        boolean_threshold: float,
    ) -> None:
        super().__init__()
        if numeric_threshold <= 0.0 or numeric_threshold > 1.0:
            raise ValueError("numeric_threshold must be in (0, 1]")
        if boolean_threshold <= 0.0 or boolean_threshold > 1.0:
            raise ValueError("boolean_threshold must be in (0, 1]")
        self._numeric_threshold = numeric_threshold
        self._boolean_threshold = boolean_threshold

    def execute(
        self,
        conn: DuckDBPyConnection,
        *,
        table_name: str = "raw_input",
        profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
        null_tokens: list[str] | None,
        boolean_true_tokens: list[str] | None,
        boolean_false_tokens: list[str] | None,
    ) -> dict[str, str]:
        start_time = perf_counter()
        token_policy = TokenPolicy.from_user_inputs(
            null_tokens=null_tokens,
            boolean_true_tokens=boolean_true_tokens,
            boolean_false_tokens=boolean_false_tokens,
        )
        profiles = ensure_column_profiles(
            conn,
            table_name=table_name,
            profile_table_name=profile_table_name,
            token_policy=token_policy,
        )

        inferred: dict[str, str] = {}
        for column_name, profile in profiles.items():
            inferred[column_name] = infer_column_type(
                profile,
                numeric_threshold=self._numeric_threshold,
                boolean_threshold=self._boolean_threshold,
            )

        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "column_count": len(inferred),
            "numeric_threshold": self._numeric_threshold,
            "boolean_threshold": self._boolean_threshold,
            "boolean_columns": sum(1 for value in inferred.values() if value == "boolean"),
            "integer_columns": sum(1 for value in inferred.values() if value == "integer"),
            "float_columns": sum(1 for value in inferred.values() if value == "float"),
            "string_columns": sum(1 for value in inferred.values() if value == "string"),
        }
        return inferred
