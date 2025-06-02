import pytest

from normalize.stages.ingestion import HeaderMode
from normalize.stages.ingestion.csv.options import (
    resolve_delimiter_option,
    resolve_encoding_option,
    resolve_header_options,
)


def test_resolve_header_options_present_mode() -> None:
    assert resolve_header_options(HeaderMode.PRESENT, 3) == (True, 2)


def test_resolve_header_options_absent_mode() -> None:
    assert resolve_header_options(HeaderMode.ABSENT, None) == (False, 0)


def test_resolve_header_options_rejects_missing_index() -> None:
    with pytest.raises(ValueError, match="MISSING_HEADER_ROW_INDEX"):
        resolve_header_options(HeaderMode.PRESENT, None)


def test_resolve_header_options_rejects_index_when_absent() -> None:
    with pytest.raises(ValueError, match="HEADER_ROW_INDEX_NOT_ALLOWED"):
        resolve_header_options(HeaderMode.ABSENT, 1)


def test_resolve_encoding_option_utf8_sig_maps_for_duckdb() -> None:
    assert resolve_encoding_option("utf-8-sig") == ("utf-8-sig", "utf-8")


def test_resolve_encoding_option_rejects_empty() -> None:
    with pytest.raises(ValueError, match="MISSING_ENCODING"):
        resolve_encoding_option("")


def test_resolve_delimiter_option_accepts_single_character() -> None:
    assert resolve_delimiter_option(";") == ";"


def test_resolve_delimiter_option_rejects_multi_character() -> None:
    with pytest.raises(ValueError, match="INVALID_DELIMITER"):
        resolve_delimiter_option(",,")
