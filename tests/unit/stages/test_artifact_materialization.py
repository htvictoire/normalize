import json
from pathlib import Path

import pyarrow.parquet as pq

from normalize.stages.artifact_materialization import ArtifactMaterializationStage
from normalize.utils.checksums import sha256_file
from shared.db.duckdb import DuckDBManager


def test_artifact_materialization_writes_expected_outputs(tmp_path: Path) -> None:
    stage = ArtifactMaterializationStage()
    fingerprint = "abc123fingerprint"

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
                (1, 'alpha', 1, 1, 0, '{"int_col":"1","text_col":"alpha"}',
                 '{"int_col":null,"text_col":null}'),
                (NULL, 'beta', 2, 2, 1, '{"int_col":"bad","text_col":"beta"}',
                 '{"int_col":"INVALID_INTEGER","text_col":null}')
            """
        )

        outputs = stage.execute(
            conn,
            output_dir=tmp_path,
            fingerprint=fingerprint,
            source_checksums={"source_file": "source-checksum"},
            stage_metrics={"ingestion": {"duration_seconds": 1.2}},
            quality_summary={"parse_success_ratio": 0.75},
            issues=[{"severity": "warning"}, {"severity": "error"}],
            effective_config={"delimiter": ","},
            rules_version="v-test",
        )

    normalized_path = Path(outputs["normalized_parquet"])
    manifest_path = Path(outputs["manifest_json"])
    trace_path = Path(outputs["trace_parquet"])

    assert normalized_path.name == f"{fingerprint}.parquet"
    assert manifest_path.name == f"{fingerprint}.manifest.json"
    assert trace_path.name == f"{fingerprint}.trace.parquet"
    assert normalized_path.exists()
    assert manifest_path.exists()
    assert trace_path.exists()

    normalized = pq.read_table(normalized_path)
    assert normalized.column_names == [
        "int_col",
        "text_col",
        "_row_index",
        "_global_row_index",
        "_raw_row",
        "_parse_issues",
    ]

    parquet_file = pq.ParquetFile(normalized_path)
    compression = parquet_file.metadata.row_group(0).column(0).compression
    assert str(compression).upper() == "ZSTD"

    trace = pq.read_table(trace_path)
    assert trace.column_names == [
        "row_index",
        "column_name",
        "raw_value",
        "normalized_value",
        "applied_rules",
        "issue_codes",
    ]
    assert trace.num_rows == 4

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["fingerprint"] == fingerprint
    assert "source_checksums" in manifest
    assert "stage_metrics" in manifest
    assert "quality_summary" in manifest
    assert "issue_summary" in manifest
    assert "artifact_checksums" in manifest
    assert "replay_instructions" in manifest
    assert "artifacts" in manifest
    assert manifest["issue_summary"]["total_count"] == 2
    assert manifest["issue_summary"]["by_severity"]["WARNING"] == 1
    assert manifest["issue_summary"]["by_severity"]["ERROR"] == 1

    assert manifest["artifact_checksums"]["normalized_parquet"] == sha256_file(normalized_path)
    assert manifest["artifact_checksums"]["trace_parquet"] == sha256_file(trace_path)
