from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.type_inference import TypeInferenceStage

COMMON_ARGS = {
    "null_tokens": ["", "null", "none", "n/a", "-"],
    "boolean_true_tokens": ["true", "yes", "1"],
    "boolean_false_tokens": ["false", "no", "0"],
}
STAGE_ARGS = {
    "numeric_threshold": 0.95,
    "boolean_threshold": 0.95,
    "currency_threshold": 0.50,
}
INFERENCE_ARGS = {
    **COMMON_ARGS,
    "decimal_separator": ".",
    "thousand_separator": ",",
    "allow_leading_decimal_point": True,
    "currency_candidate_threshold": 0.95,
    "date_formats": {},
}


def test_type_inference_basic_types() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col VARCHAR,
                float_col VARCHAR,
                bool_col VARCHAR,
                text_col VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1', '1.1', 'true', 'hello'),
                ('2', '2.2', 'false', 'world'),
                ('3', '3.3', 'true', 'data')
            """
        )

        inferred = stage.execute(conn, **INFERENCE_ARGS)
        assert inferred == {
            "int_col": "integer",
            "float_col": "decimal",
            "bool_col": "boolean",
            "text_col": "string",
        }


def test_type_inference_below_threshold_falls_back_to_string() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (mixed_col VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1'),
                ('hello'),
                ('hello')
            """
        )
        inferred = stage.execute(conn, **INFERENCE_ARGS)
        assert inferred == {"mixed_col": "string"}


def test_type_inference_mixed_integers_and_floats_prefers_float() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (num_col VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1'),
                ('2.5'),
                ('3'),
                ('4.1')
            """
        )
        inferred = stage.execute(conn, **INFERENCE_ARGS)
        assert inferred == {"num_col": "decimal"}


def test_type_inference_boolean_requires_full_token_match() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (boolish VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('true'),
                ('false'),
                ('maybe')
            """
        )
        inferred = stage.execute(conn, **INFERENCE_ARGS)
        assert inferred == {"boolish": "string"}


def test_type_inference_supports_eu_separators() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1.234,56'),
                ('2.000,10'),
                ('3.999,00')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=",",
            thousand_separator=".",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={},
        )
        assert inferred == {"amount": "decimal"}


def test_type_inference_emits_separator_mismatch_issue() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1.234,56'),
                ('2.000,10'),
                ('3.999,00')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={},
        )
        assert inferred == {"amount": "string"}
        issues = stage.detected_issues
        assert len(issues) == 1
        assert issues[0].code == "SEPARATOR_MISMATCH"
        assert issues[0].severity.value == "WARNING"


def test_type_inference_declares_date_by_position_and_warns_unknown_position() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (tx_date VARCHAR, value VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('31/12/2025', '100'),
                ('01/01/2026', '101')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={"A": "%d/%m/%Y", "Z": "%Y-%m-%d"},
        )
        assert inferred == {"tx_date": "date", "value": "integer"}
        assert [issue.code for issue in stage.detected_issues] == [
            "UNKNOWN_COLUMN_REFERENCE"
        ]


def test_type_inference_resolves_date_columns_by_table_order() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (tx_date VARCHAR, value VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('31/12/2025', '100'),
                ('01/01/2026', '101')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={"A": "%d/%m/%Y"},
        )
        assert inferred == {"tx_date": "date", "value": "integer"}


def test_type_inference_leading_decimal_point_toggle() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('.5'),
                ('-.9'),
                ('.25')
            """
        )
        inferred_allow = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={},
        )
        assert inferred_allow == {"amount": "decimal"}

    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('.5'),
                ('-.9'),
                ('.25')
            """
        )
        inferred_disallow = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=False,
            currency_candidate_threshold=0.95,
            date_formats={},
        )

    assert inferred_disallow == {"amount": "string"}


def test_type_inference_supports_trailing_decimal_and_plus_sign() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('5.'),
                ('+1.5'),
                ('2.0')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={},
        )
        assert inferred == {"amount": "decimal"}


def test_type_inference_with_empty_thousand_separator() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1000'),
                ('5.5'),
                ('3')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator="",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={},
        )
        assert inferred == {"amount": "decimal"}


def test_type_inference_detects_currency_with_symbol_and_bare_values() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('$1,200.50'),
                ('EUR 99.90'),
                ('CNY 88.20'),
                ('A$ 77.10'),
                ('100.00')
            """
        )
        inferred = stage.execute(
            conn,
            **COMMON_ARGS,
            decimal_separator=".",
            thousand_separator=",",
            allow_leading_decimal_point=True,
            currency_candidate_threshold=0.95,
            date_formats={},
        )
        assert inferred == {"amount": "currency"}


def test_type_inference_keeps_integer_priority_over_currency() -> None:
    stage = TypeInferenceStage(**STAGE_ARGS)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (amount VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('100'),
                ('200'),
                ('300')
            """
        )
        inferred = stage.execute(conn, **INFERENCE_ARGS)
        assert inferred == {"amount": "integer"}
