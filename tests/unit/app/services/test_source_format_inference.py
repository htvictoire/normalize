from suggestion.source_format import infer_source_format_from_bytes


def test_infer_source_format_comma_decimal_dot() -> None:
    sample = b"Order ID,Amount,Name\n1,1234.56,Alice\n2,789.10,Bob\n"

    inferred = infer_source_format_from_bytes(sample)

    assert inferred.encoding == "utf-8"
    assert inferred.delimiter == ","
    assert inferred.header_mode == "present"
    assert inferred.header_row_index == 1


def test_infer_source_format_semicolon_decimal_comma() -> None:
    sample = b"order_id;amount;name\n1;1.234,56;Alice\n2;789,10;Bob\n"

    inferred = infer_source_format_from_bytes(sample)

    assert inferred.delimiter == ";"
    assert inferred.header_mode == "present"
    assert inferred.header_row_index == 1
