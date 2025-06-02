from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.type_inference import TypeInferenceStage

TOKEN_ARGS = {
    "null_tokens": ["", "null", "none", "n/a", "-"],
    "boolean_true_tokens": ["true", "yes", "1"],
    "boolean_false_tokens": ["false", "no", "0"],
}


def test_type_inference_basic_types() -> None:
    stage = TypeInferenceStage(numeric_threshold=0.95, boolean_threshold=0.95)
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

        inferred = stage.execute(conn, **TOKEN_ARGS)
        assert inferred == {
            "int_col": "integer",
            "float_col": "float",
            "bool_col": "boolean",
            "text_col": "string",
        }


def test_type_inference_below_threshold_falls_back_to_string() -> None:
    stage = TypeInferenceStage(numeric_threshold=0.95, boolean_threshold=0.95)
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (mixed_col VARCHAR)")
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1'),
                ('2'),
                ('hello')
            """
        )
        inferred = stage.execute(conn, **TOKEN_ARGS)
        assert inferred == {"mixed_col": "string"}


def test_type_inference_mixed_integers_and_floats_prefers_float() -> None:
    stage = TypeInferenceStage(numeric_threshold=0.95, boolean_threshold=0.95)
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
        inferred = stage.execute(conn, **TOKEN_ARGS)
        assert inferred == {"num_col": "float"}


def test_type_inference_boolean_requires_full_token_match() -> None:
    stage = TypeInferenceStage(numeric_threshold=0.95, boolean_threshold=0.95)
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
        inferred = stage.execute(conn, **TOKEN_ARGS)
        assert inferred == {"boolish": "string"}
