from assetserve import content_type


def test_csv_export_content_type():
    assert content_type("q3-report.csv") == "text/csv"


def test_dotfile_is_not_served_as_text():
    assert content_type(".env") == "application/octet-stream"
