from logsafe import redact


def test_nested_secrets_masked():
    out = redact({"request": {"user_password": "x", "api_key": "k"}, "id": 7})
    assert out["request"]["user_password"] == "***"
    assert out["request"]["api_key"] == "***"
    assert out["id"] == 7
