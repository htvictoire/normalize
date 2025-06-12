import hashlib

import pytest

from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.ingestion import HeaderMode, IngestionRequest, run_ingestion


def test_service_loads_small_file(tmp_path) -> None:
    csv_path = tmp_path / "small.csv"
    csv_path.write_text("Name,Age\nAlice,30\nBob,41\n", encoding="utf-8")

    with DuckDBManager() as conn:
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="utf-8",
                delimiter=",",
            )
        )
        assert result.row_count == 2
        assert conn.execute("SELECT COUNT(*) FROM raw_input").fetchone()[0] == 2


def test_service_loads_large_file(tmp_path) -> None:
    csv_path = tmp_path / "large.csv"
    csv_path.write_text("id\n" + ("1\n" * 1000), encoding="utf-8")

    with DuckDBManager() as conn:
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="utf-8",
                delimiter=",",
            )
        )
        assert result.row_count == 1000
        assert conn.execute("SELECT COUNT(*) FROM raw_input").fetchone()[0] == 1000


def test_service_supports_latin1_input(tmp_path) -> None:
    csv_path = tmp_path / "latin1.csv"
    csv_path.write_bytes("Name,Age\nJosé,30\n".encode("latin-1"))

    with DuckDBManager() as conn:
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="latin-1",
                delimiter=",",
            )
        )
        assert result.row_count == 1
        assert conn.execute("SELECT Name FROM raw_input").fetchone()[0] == "José"


def test_service_computes_checksum_from_file_bytes(tmp_path) -> None:
    csv_path = tmp_path / "small.csv"
    payload = "id\n1\n"
    csv_path.write_text(payload, encoding="utf-8")

    with DuckDBManager() as conn:
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="utf-8",
                delimiter=",",
            )
        )
        assert result.file_checksum == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_service_supports_explicit_absent_header_mode(tmp_path) -> None:
    csv_path = tmp_path / "no_header.csv"
    csv_path.write_text("Alice,30\nBob,41\n", encoding="utf-8")

    with DuckDBManager() as conn:
        result = run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.ABSENT,
                header_row_index=None,
                encoding="utf-8",
                delimiter=",",
            )
        )
        assert result.row_count == 2
        assert result.column_names == ["column0", "column1"]


def test_service_rejects_missing_header_row_for_present_mode(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name\nalice\n", encoding="utf-8")

    with DuckDBManager() as conn, pytest.raises(ValueError, match="MISSING_HEADER_ROW_INDEX"):
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=None,
                encoding="utf-8",
                delimiter=",",
            )
        )


def test_service_rejects_header_row_in_absent_mode(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name\nalice\n", encoding="utf-8")

    with DuckDBManager() as conn, pytest.raises(ValueError, match="HEADER_ROW_INDEX_NOT_ALLOWED"):
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.ABSENT,
                header_row_index=1,
                encoding="utf-8",
                delimiter=",",
            )
        )


def test_service_rejects_missing_encoding(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name\nalice\n", encoding="utf-8")

    with DuckDBManager() as conn, pytest.raises(ValueError, match="MISSING_ENCODING"):
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="",
                delimiter=",",
            )
        )


def test_service_rejects_unsupported_encoding(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name\nalice\n", encoding="utf-8")

    with DuckDBManager() as conn, pytest.raises(ValueError, match="UNSUPPORTED_ENCODING"):
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="cp1252",
                delimiter=",",
            )
        )


def test_service_rejects_invalid_delimiter(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name\nalice\n", encoding="utf-8")

    with DuckDBManager() as conn, pytest.raises(ValueError, match="INVALID_DELIMITER"):
        run_ingestion(
            IngestionRequest(
                conn=conn,
                csv_path=csv_path,
                header_mode=HeaderMode.PRESENT,
                header_row_index=1,
                encoding="utf-8",
                delimiter=",,",
            )
        )
