import json

import pytest

from normalize.core.column_config import (
    BooleanColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    StringColumnConfig,
)
from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.cell_normalization import CellNormalizationStage

COMMON_ARGS = {
    "null_tokens": ["", "null", "none", "n/a", "-"],
    "boolean_true_tokens": ["true", "yes", "1"],
    "boolean_false_tokens": ["false", "no", "0"],
}


def _integer_config(
    *,
    decimal_separator: str = ".",
    thousand_separator: str = ",",
    grouping_style: str = "western",
) -> IntegerColumnConfig:
    return IntegerColumnConfig(
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
    )


def _decimal_config(
    *,
    decimal_separator: str = ".",
    thousand_separator: str = ",",
    grouping_style: str = "western",
    allow_leading_decimal_point: bool = False,
) -> DecimalColumnConfig:
    return DecimalColumnConfig(
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )


def _currency_config(
    *,
    decimal_separator: str = ".",
    thousand_separator: str = ",",
    grouping_style: str = "western",
    allow_leading_decimal_point: bool = False,
) -> CurrencyColumnConfig:
    return CurrencyColumnConfig(
        decimal_separator=decimal_separator,
        thousand_separator=thousand_separator,
        grouping_style=grouping_style,
        allow_leading_decimal_point=allow_leading_decimal_point,
    )


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

        column_config = {
            "int_col": _integer_config(),
            "float_col": _decimal_config(),
            "bool_col": BooleanColumnConfig(),
            "text_col": StringColumnConfig(),
        }
        stage.execute(conn, column_config=column_config, **COMMON_ARGS)

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
        with pytest.raises(ValueError, match="MISSING_COLUMN_CONFIG"):
            stage.execute(conn, column_config={"a": _integer_config()}, **COMMON_ARGS)


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
            column_config={"bool_col": BooleanColumnConfig()},
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
            column_config={
                "int_col": _integer_config(),
                "text_col": StringColumnConfig(),
            },
            **COMMON_ARGS,
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
            column_config={"int_col": _integer_config()},
            emit_raw_row=False,
            emit_parse_issues=False,
            **COMMON_ARGS,
        )

        rows = conn.execute(
            """
            SELECT int_col, _parse_error_count, _raw_row, _parse_issues
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()
        assert rows == [(None, 1, None, None), (2, 0, None, None)]


def test_cell_normalization_normalizes_decimal_with_declared_separators() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('1.234,56', 1, 1),
                ('2.000,10', 2, 2)
            """
        )
        stage.execute(
            conn,
            column_config={
                "amount": _decimal_config(
                    decimal_separator=",",
                    thousand_separator=".",
                )
            },
            **COMMON_ARGS,
        )
        rows = conn.execute("SELECT amount FROM raw_input ORDER BY _row_index").fetchall()
        assert rows == [(1234.56,), (2000.1,)]


def test_cell_normalization_parses_declared_dates_and_flags_invalid_date() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                tx_date VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('31/12/2025', 1, 1),
                ('invalid', 2, 2)
            """
        )
        stage.execute(
            conn,
            column_config={"tx_date": DateColumnConfig(date_format="%d/%m/%Y")},
            **COMMON_ARGS,
        )
        rows = conn.execute(
            """
            SELECT tx_date, _parse_error_count, _parse_issues
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()
        assert str(rows[0][0]) == "2025-12-31"
        assert rows[0][1] == 0
        assert rows[1][0] is None
        assert rows[1][1] == 1
        issue_payload = json.loads(rows[1][2])
        assert issue_payload["tx_date"] == "INVALID_DATE"


def test_cell_normalization_leading_decimal_point_toggle() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute("INSERT INTO raw_input VALUES ('.5', 1, 1)")

        stage.execute(
            conn,
            column_config={"amount": _decimal_config(allow_leading_decimal_point=False)},
            **COMMON_ARGS,
        )
        strict_row = conn.execute(
            "SELECT amount, _parse_error_count, _parse_issues FROM raw_input"
        ).fetchone()
        assert strict_row is not None
        assert strict_row[0] is None
        assert strict_row[1] == 1
        strict_issues = json.loads(strict_row[2])
        assert strict_issues["amount"] == "INVALID_DECIMAL"

    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute("INSERT INTO raw_input VALUES ('.5', 1, 1)")
        stage.execute(
            conn,
            column_config={"amount": _decimal_config(allow_leading_decimal_point=True)},
            **COMMON_ARGS,
        )
        relaxed_row = conn.execute(
            "SELECT amount, _parse_error_count FROM raw_input"
        ).fetchone()
        assert relaxed_row == (0.5, 0)


def test_cell_normalization_resolves_date_formats_by_table_order() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                tx_date VARCHAR,
                value VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('31/12/2025', 'ok', 1, 1)
            """
        )
        stage.execute(
            conn,
            column_config={
                "tx_date": DateColumnConfig(date_format="%d/%m/%Y"),
                "value": StringColumnConfig(),
            },
            **COMMON_ARGS,
        )
        row = conn.execute("SELECT tx_date, _parse_error_count FROM raw_input").fetchone()
        assert row is not None
        assert str(row[0]) == "2025-12-31"
        assert row[1] == 0


def test_cell_normalization_supports_trailing_decimal_and_plus_sign() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('5.', 1, 1),
                ('+1.5', 2, 2)
            """
        )
        stage.execute(
            conn,
            column_config={"amount": _decimal_config(allow_leading_decimal_point=True)},
            **COMMON_ARGS,
        )
        rows = conn.execute(
            "SELECT amount, _parse_error_count FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert rows == [(5.0, 0), (1.5, 0)]


def test_cell_normalization_with_empty_thousand_separator() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('5.5', 1, 1),
                ('1000', 2, 2)
            """
        )
        stage.execute(
            conn,
            column_config={
                "amount": _decimal_config(
                    thousand_separator="",
                    allow_leading_decimal_point=True,
                )
            },
            **COMMON_ARGS,
        )
        rows = conn.execute(
            "SELECT amount, _parse_error_count FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert rows == [(5.5, 0), (1000.0, 0)]


def test_cell_normalization_normalizes_currency_and_accounting_notation() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('$1,234.56', 1, 1),
                ('(100.00)', 2, 2),
                ('100.00-', 3, 3),
                ('100.00 CR', 4, 4),
                ('100.00 DR', 5, 5),
                ('EUR 50.00', 6, 6),
                ('CNY 75.25', 7, 7),
                ('A$ 90.10', 8, 8)
            """
        )
        stage.execute(
            conn,
            column_config={
                "amount": _currency_config(allow_leading_decimal_point=True),
            },
            **COMMON_ARGS,
        )
        rows = conn.execute(
            "SELECT amount, _parse_error_count FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert rows == [
            (1234.56, 0),
            (-100.0, 0),
            (-100.0, 0),
            (-100.0, 0),
            (100.0, 0),
            (50.0, 0),
            (75.25, 0),
            (90.1, 0),
        ]


def test_cell_normalization_emits_invalid_currency_issue() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('$10.00', 1, 1),
                ('INVALID', 2, 2)
            """
        )
        stage.execute(
            conn,
            column_config={
                "amount": _currency_config(allow_leading_decimal_point=True),
            },
            **COMMON_ARGS,
        )
        rows = conn.execute(
            "SELECT amount, _parse_error_count, _parse_issues FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert rows[0][0:2] == (10.0, 0)
        assert rows[1][0] is None
        assert rows[1][1] == 1
        issues = json.loads(rows[1][2])
        assert issues["amount"] == "INVALID_CURRENCY"


def test_cell_normalization_honors_per_column_currency_separators() -> None:
    stage = CellNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                amount VARCHAR,
                _row_index BIGINT,
                _global_row_index BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('NOK 32,43', 1, 1),
                ('NOK 1.234,50', 2, 2),
                ('NOK 99,00', 3, 3)
            """
        )
        stage.execute(
            conn,
            column_config={
                "amount": _currency_config(
                    decimal_separator=",",
                    thousand_separator=".",
                    grouping_style="western",
                    allow_leading_decimal_point=True,
                )
            },
            **COMMON_ARGS,
        )
        rows = conn.execute(
            "SELECT amount, _parse_error_count FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert rows == [(32.43, 0), (1234.5, 0), (99.0, 0)]
