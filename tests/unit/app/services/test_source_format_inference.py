from pathlib import Path

from suggestion.source_format import infer_source_format


def test_infer_source_format_comma_decimal_dot(tmp_path: Path) -> None:
    csv_path = tmp_path / "us.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Order ID,Amount,Name",
                "1,1234.56,Alice",
                "2,789.10,Bob",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    inferred = infer_source_format(csv_path)

    assert inferred.encoding == "utf-8"
    assert inferred.delimiter == ","
    assert inferred.header_mode == "present"
    assert inferred.header_row_index == 1


def test_infer_source_format_semicolon_decimal_comma(tmp_path: Path) -> None:
    csv_path = tmp_path / "eu.csv"
    csv_path.write_text(
        "\n".join(
            [
                "order_id;amount;name",
                "1;1.234,56;Alice",
                "2;789,10;Bob",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    inferred = infer_source_format(csv_path)

    assert inferred.delimiter == ";"
    assert inferred.header_mode == "present"
    assert inferred.header_row_index == 1
