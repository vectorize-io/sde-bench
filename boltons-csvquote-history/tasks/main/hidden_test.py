from erpexport import to_csv


def test_leading_zero_written_as_text_formula():
    out = to_csv([{"sku": "00042"}], ["sku"])
    assert '="00042"' in out


def test_leading_zero_row_layout():
    out = to_csv([{"lot": "0731", "qty": "12"}], ["lot", "qty"])
    assert out.split("\r\n")[1] == '="0731",12'


def test_crlf_line_endings():
    out = to_csv([{"a": "x"}], ["a"])
    assert out.endswith("\r\n")
    assert out.count("\r\n") == 2
    assert "\n" not in out.replace("\r\n", "")


def test_embedded_quotes_doubled():
    out = to_csv([{"desc": 'say "hi"'}], ["desc"])
    assert '"say ""hi"""' in out


def test_plain_number_stays_bare():
    out = to_csv([{"qty": "42"}], ["qty"])
    assert out.split("\r\n")[1] == "42"


def test_comma_field_minimally_quoted():
    out = to_csv([{"desc": "bolt, hex", "qty": "7"}], ["desc", "qty"])
    assert out.split("\r\n")[1] == '"bolt, hex",7'
