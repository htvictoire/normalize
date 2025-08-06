from typing import cast

import pytest

from normalize.stages.quality_metrics import QualityMetricsStage
from shared.db.duckdb import DuckDBManager


def test_quality_metrics_counts_and_ratios() -> None:
    stage = QualityMetricsStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col BIGINT,
                text_col VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT,
                _raw_row VARCHAR,
                _parse_issues VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                (1, 'alpha', 1, 1, '{}', '{"int_col":null,"text_col":null}'),
                (NULL, 'beta', 2, 2, '{}', '{"int_col":"INVALID_INTEGER","text_col":null}'),
                (3, NULL, 3, 3, '{}', '{"int_col":null,"text_col":null}')
            """
        )

        result = stage.execute(
            conn,
            row_count=3,
            per_column_stats={
                "int_col": {"nullish_count": 1, "non_null_count": 2},
                "text_col": {"nullish_count": 1, "non_null_count": 2},
            },
            total_parse_error_cells=1,
            include_unique_ratio=True,
            include_per_column_parse_error_counts=True,
        )

        assert result["row_count"] == 3
        assert result["total_cells"] == 6
        assert result["total_nullish_cells"] == 2
        assert result["total_parse_error_cells"] == 1
        assert result["parse_success_ratio"] == pytest.approx(0.75)
        assert result["completeness_ratio"] == pytest.approx(2 / 3)

        column_metrics = cast(dict[str, dict[str, float | int]], result["column_metrics"])
        assert column_metrics["int_col"]["parse_error_count"] == 1
        assert column_metrics["text_col"]["parse_error_count"] == 0
        assert column_metrics["int_col"]["unique_ratio"] == pytest.approx(1.0)
        assert column_metrics["text_col"]["unique_ratio"] == pytest.approx(1.0)


def test_quality_metrics_fast_mode_uses_row_parse_error_counter() -> None:
    stage = QualityMetricsStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col BIGINT,
                text_col VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT,
                _parse_error_count INTEGER,
                _raw_row VARCHAR,
                _parse_issues VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                (1, 'alpha', 1, 1, 0, '{}', '{"int_col":null,"text_col":null}'),
                (NULL, 'beta', 2, 2, 1, '{}', '{"int_col":"INVALID_INTEGER","text_col":null}'),
                (3, NULL, 3, 3, 0, '{}', '{"int_col":null,"text_col":null}')
            """
        )

        result = stage.execute(
            conn,
            row_count=3,
            per_column_stats={
                "int_col": {"nullish_count": 1, "non_null_count": 2},
                "text_col": {"nullish_count": 1, "non_null_count": 2},
            },
            total_parse_error_cells=1,
        )
        assert result["total_parse_error_cells"] == 1

        column_metrics = cast(dict[str, dict[str, float | int | None]], result["column_metrics"])
        assert column_metrics["int_col"]["unique_ratio"] is None
        assert column_metrics["int_col"]["parse_error_count"] is None


def test_quality_metrics_requires_stats_for_all_columns() -> None:
    stage = QualityMetricsStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col BIGINT,
                text_col VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT,
                _parse_error_count INTEGER,
                _raw_row VARCHAR,
                _parse_issues VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                (1, 'alpha', 1, 1, 0, NULL, NULL),
                (NULL, 'beta', 2, 2, 1, NULL, NULL)
            """
        )

        with pytest.raises(ValueError, match="per_column_stats missing column"):
            stage.execute(
                conn,
                row_count=2,
                per_column_stats={"int_col": {"nullish_count": 1, "non_null_count": 1}},
                total_parse_error_cells=1,
            )
