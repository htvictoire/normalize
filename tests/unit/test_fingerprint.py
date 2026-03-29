from conversion.fingerprint import compute_fingerprint


def test_fingerprint_is_stable_for_same_inputs() -> None:
    value1 = compute_fingerprint(
        "source-checksum",
        '{"delimiter":","}',
        "duckdb-1.0.0",
    )
    value2 = compute_fingerprint(
        "source-checksum",
        '{"delimiter":","}',
        "duckdb-1.0.0",
    )
    assert value1 == value2


def test_fingerprint_changes_when_input_changes() -> None:
    baseline = compute_fingerprint(
        "source-checksum",
        '{"delimiter":","}',
        "duckdb-1.0.0",
    )
    changed = compute_fingerprint(
        "source-checksum-2",
        '{"delimiter":","}',
        "duckdb-1.0.0",
    )
    assert baseline != changed
