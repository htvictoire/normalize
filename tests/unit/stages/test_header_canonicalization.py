from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.header_canonicalization import HeaderCanonicalizationStage


def test_header_canonicalization_rules_and_uniqueness() -> None:
    stage = HeaderCanonicalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                "  First Name  " VARCHAR,
                "Amount ($)" VARCHAR,
                "___weird___" VARCHAR,
                "Name " VARCHAR,
                "Name!" VARCHAR,
                "already_clean" VARCHAR
            )
            """
        )
        mapping = stage.execute(conn)

        assert mapping == {
            "  First Name  ": "first_name",
            "Amount ($)": "amount",
            "___weird___": "weird",
            "Name ": "name",
            "Name!": "name_2",
            "already_clean": "already_clean",
        }
        columns = [row[1] for row in conn.execute("PRAGMA table_info('raw_input')").fetchall()]
        assert columns == ["first_name", "amount", "weird", "name", "name_2", "already_clean"]


def test_header_canonicalization_fallback_for_empty_result() -> None:
    stage = HeaderCanonicalizationStage()
    with DuckDBManager() as conn:
        conn.execute(
            """
            CREATE TABLE raw_input (
                "$$$" VARCHAR,
                "___" VARCHAR
            )
            """
        )
        mapping = stage.execute(conn)
        assert mapping == {"$$$": "column", "___": "column_2"}
        columns = [row[1] for row in conn.execute("PRAGMA table_info('raw_input')").fetchall()]
        assert columns == ["column", "column_2"]
