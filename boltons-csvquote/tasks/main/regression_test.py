import csv

from erpexport import to_csv


def test_comma_value_stays_in_one_column():
    out = to_csv([{"desc": "bolt, hex", "qty": "5"}], ["desc", "qty"])
    rows = list(csv.reader(out.splitlines()))
    assert rows[1] == ["bolt, hex", "5"]
