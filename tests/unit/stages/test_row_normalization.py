from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.row_normalization import RowNormalizationStage


def test_row_normalization_drops_empty_rows_and_adds_indices() -> None:
    stage = RowNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                name VARCHAR,
                value VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('alpha', '10'),
                ('', ''),
                ('beta', '20'),
                ('   ', NULL),
                ('gamma', '30'),
                ('delta', '40'),
                ('epsilon', '50')
            """
        )

        result = stage.execute(conn)

        assert result == {"rows_before": 7, "rows_after": 5, "rows_dropped": 2}
        rows = conn.execute(
            """
            SELECT name, value, _row_index, _global_row_index
            FROM raw_input
            ORDER BY _row_index
            """
        ).fetchall()
        assert rows == [
            ("alpha", "10", 1, 1),
            ("beta", "20", 2, 2),
            ("gamma", "30", 3, 3),
            ("delta", "40", 4, 4),
            ("epsilon", "50", 5, 5),
        ]


def test_row_normalization_treats_whitespace_only_rows_as_empty() -> None:
    stage = RowNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                left_col VARCHAR,
                right_col VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('   ', '\t'),
                ('ok', 'value')
            """
        )

        result = stage.execute(conn)
        assert result == {"rows_before": 2, "rows_after": 1, "rows_dropped": 1}
        assert conn.execute("SELECT left_col, right_col, _row_index FROM raw_input").fetchall() == [
            ("ok", "value", 1)
        ]


def test_row_normalization_preserves_row_order() -> None:
    stage = RowNormalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                event_id VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('evt-3'),
                ('evt-1'),
                (''),
                ('evt-2')
            """
        )

        stage.execute(conn)
        ordered = conn.execute(
            "SELECT event_id, _row_index FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert ordered == [("evt-3", 1), ("evt-1", 2), ("evt-2", 3)]


def test_row_normalization_can_skip_index_materialization() -> None:
    stage = RowNormalizationStage(assign_indices=False)
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                name VARCHAR,
                value VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('alpha', '10'),
                ('', ''),
                ('beta', '20')
            """
        )

        result = stage.execute(conn)
        assert result == {"rows_before": 3, "rows_after": 2, "rows_dropped": 1}
        rows = conn.execute("SELECT name, value FROM raw_input ORDER BY rowid").fetchall()
        assert rows == [("alpha", "10"), ("beta", "20")]
        columns = [row[1] for row in conn.execute("PRAGMA table_info('raw_input')").fetchall()]
        assert "_row_index" not in columns
        assert "_global_row_index" not in columns


def test_row_normalization_can_skip_empty_row_filter_for_trusted_inputs() -> None:
    stage = RowNormalizationStage(assign_indices=True, drop_empty_rows=False)
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                name VARCHAR,
                value VARCHAR
            )
            """
        )
        conn.execute(
            """
            INSERT INTO raw_input VALUES
                ('alpha', '10'),
                ('', ''),
                ('beta', '20')
            """
        )

        result = stage.execute(conn)
        assert result == {"rows_before": 3, "rows_after": 3, "rows_dropped": 0}
        rows = conn.execute(
            "SELECT name, value, _row_index, _global_row_index FROM raw_input ORDER BY _row_index"
        ).fetchall()
        assert rows == [("alpha", "10", 1, 1), ("", "", 2, 2), ("beta", "20", 3, 3)]
