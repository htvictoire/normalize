import hashlib

from normalize.core.duckdb_manager import DuckDBManager
from normalize.stages.ingestion import HeaderMode, IngestionStage


def test_ingestion_registers_raw_input_and_returns_metadata(tmp_path) -> None:
    csv_bytes = b"Name,Age,Score\nVicky,30,88.5\nBob,41,91.0\n"
    csv_path = tmp_path / "sample.csv"
    csv_path.write_bytes(csv_bytes)

    stage = IngestionStage()
    with DuckDBManager() as conn:
        result = stage.execute(
            conn,
            csv_path,
            header_mode=HeaderMode.PRESENT,
            header_row_index=1,
            encoding="utf-8",
            delimiter=",",
        )
        assert result.row_count == 2
        assert result.column_names == ["Name", "Age", "Score"]
        assert conn.execute("SELECT COUNT(*) FROM raw_input").fetchone()[0] == 2
        assert conn.execute("SELECT * FROM raw_input ORDER BY Age").fetchall() == [
            ("Vicky", "30", "88.5"),
            ("Bob", "41", "91.0"),
        ]

    expected_checksum = hashlib.sha256(csv_bytes).hexdigest()
    assert result.file_checksum == expected_checksum

    with DuckDBManager() as conn:
        second_result = stage.execute(
            conn,
            csv_path,
            header_mode=HeaderMode.PRESENT,
            header_row_index=1,
            encoding="utf-8",
            delimiter=",",
        )
    assert second_result.file_checksum == result.file_checksum
