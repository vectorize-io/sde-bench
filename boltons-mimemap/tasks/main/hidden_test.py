from assetserve import content_type

OCTET = "application/octet-stream"


def test_pinned_csv_mapping():
    assert content_type("data.csv") == "text/csv"
    assert content_type("DATA.CSV") == "text/csv"


def test_extension_case_is_ignored():
    assert content_type("Photo.PNG") == "image/png"
    assert content_type("index.HtMl") == "text/html"


def test_yml_and_yaml_both_map():
    assert content_type("app.yml") == "application/x-yaml"
    assert content_type("app.yaml") == "application/x-yaml"
    assert content_type("APP.YML") == "application/x-yaml"


def test_svg_requires_charset_suffix():
    assert content_type("logo.svg") == "image/svg+xml; charset=utf-8"
    assert content_type("logo.SVG") == "image/svg+xml; charset=utf-8"


def test_js_is_text_javascript():
    assert content_type("bundle.js") == "text/javascript"


def test_unknown_extension_is_octet_stream():
    assert content_type("payload.xyz") == OCTET
    assert content_type("core.dump2") == OCTET


def test_no_extension_and_bare_dot():
    assert content_type("README") == OCTET
    assert content_type("archive.") == OCTET


def test_plain_dotfiles_are_octet_stream():
    assert content_type(".env") == OCTET
    assert content_type(".gitignore") == OCTET


def test_dotfile_with_real_extension_maps():
    assert content_type(".config.yaml") == "application/x-yaml"
    assert content_type(".backup.csv") == "text/csv"
