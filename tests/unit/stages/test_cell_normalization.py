import json

from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.cell_normalization import CellNormalizationStage

TOKEN_ARGS = {
    "null_tokens": ["", "null", "none", "n/a", "-"],
    "boolean_true_tokens": ["true", "yes", "1"],
    "boolean_false_tokens": ["false", "no", "0"],
}


def test_cell_normalization_applies_casts_and_issue_codes() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col VARCHAR,
                float_col VARCHAR,
                bool_col VARCHAR,
                text_col VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('42', '1.5', 'true', 'hello', 1, 1),
                ('not_a_number', '2.5', 'maybe', 'world', 2, 2),
                ('null', 'n/a', '-', '', 3, 3)
            """
        )

        inferred = {
            "int_col": "integer",
            "float_col": "float",
            "bool_col": "boolean",
            "text_col": "string",
        }
        stage.execute(conn, inferred, **TOKEN_ARGS)

        rows = conn.execute(
            """
            SELECT
                int_col,
                float_col,
                bool_col,
                text_col,
                _row_index,
                _global_row_index,
                _raw_row,
                _parse_issues
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()

        assert rows[0][0:6] == (42, 1.5, True, "hello", 1, 1)
        assert rows[1][0:6] == (None, 2.5, None, "world", 2, 2)
        assert rows[2][0:6] == (None, None, None, None, 3, 3)

        raw_payload = json.loads(rows[1][6])
        assert raw_payload["int_col"] == "not_a_number"
        issue_payload = json.loads(rows[1][7])
        assert issue_payload["int_col"] == "INVALID_INTEGER"
        assert issue_payload["bool_col"] == "INVALID_BOOLEAN"
        assert issue_payload["float_col"] is None


def test_cell_normalization_rejects_missing_inferred_column() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute("CREATE TABLE raw_input (a VARCHAR, b VARCHAR)")
        conn.execute("INSERT INTO raw_input VALUES ('1', '2')")
        try:
            stage.execute(conn, {"a": "integer"}, **TOKEN_ARGS)
            raise AssertionError("Expected missing inferred type error")
        except ValueError as error:
            assert "MISSING_INFERRED_TYPES" in str(error)


def test_cell_normalization_applies_user_defined_boolean_tokens() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                bool_col VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('YES', 1, 1),
                ('no', 2, 2)
            """
        )
        stage.execute(
            conn,
            {"bool_col": "boolean"},
            null_tokens=["", "null"],
            boolean_true_tokens=["yes"],
            boolean_false_tokens=["no"],
        )
        rows = conn.execute("SELECT bool_col FROM raw_input ORDER BY _row_index").fetchall()
        assert rows == [(True,), (False,)]


def test_cell_normalization_materializes_indices_when_missing() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col VARCHAR,
                text_col VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1', 'a'),
                ('2', 'b')
            """
        )
        stage.execute(
            conn,
            {"int_col": "integer", "text_col": "string"},
            **TOKEN_ARGS,
        )
        rows = conn.execute(
            """
            SELECT int_col, text_col, _row_index, _global_row_index
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()
        assert rows == [(1, "a", 1, 1), (2, "b", 2, 2)]


def test_cell_normalization_can_disable_audit_json_payloads() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                int_col VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('bad', 1, 1),
                ('2', 2, 2)
            """
        )

        stage.execute(
            conn,
            {"int_col": "integer"},
            emit_raw_row=False,
            emit_parse_issues=False,
            **TOKEN_ARGS,
        )

        rows = conn.execute(
            """
            SELECT int_col, _parse_error_count, _raw_row, _parse_issues
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()
        assert rows == [(None, 1, None, None), (2, 0, None, None)]
