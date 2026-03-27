from shared.db.duckdb import DuckDBManager

from conversion.stages.header_canonicalization import (
    HeaderCanonicalizationStage,
    canonicalize_header_sequence,
    canonicalize_headers,
)


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
        assert stage.position_to_canonical == {
            "A": "first_name",
            "B": "amount",
            "C": "weird",
            "D": "name",
            "E": "name_2",
            "F": "already_clean",
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
        assert stage.position_to_canonical == {"A": "column", "B": "column_2"}
        columns = [row[1] for row in conn.execute("PRAGMA table_info('raw_input')").fetchall()]
        assert columns == ["column", "column_2"]


def test_canonicalize_header_sequence_handles_duplicate_raw_names_by_position() -> None:
    canonical = canonicalize_header_sequence(["Date", "Date", "Amount", "Date"])
    assert canonical == ["date", "date_2", "amount", "date_3"]


def test_canonicalize_headers_disambiguates_duplicate_raw_mapping_keys() -> None:
    mapping = canonicalize_headers(["Date", "Date", "Amount", "Date"])
    assert mapping == {
        "Date#1": "date",
        "Date#2": "date_2",
        "Amount": "amount",
        "Date#3": "date_3",
    }
