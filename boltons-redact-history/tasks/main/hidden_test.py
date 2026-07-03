from logsafe import redact


def test_card_number_keeps_tail():
    out = redact({"card_number": "4111111111111234"})
    assert out["card_number"] == "***1234"


def test_card_number_suffix_nested():
    out = redact({"payment": {"customer_card_number": "5555444433331111"}})
    assert out["payment"]["customer_card_number"] == "***1111"


def test_email_not_masked():
    out = redact({"email": "a@b.com", "user": {"contact_email": "c@d.com"}})
    assert out["email"] == "a@b.com"
    assert out["user"]["contact_email"] == "c@d.com"


def test_suffix_and_normalization():
    out = redact({"X-Api-Key": "k", "user_ssn": "123-45-6789", "auth_token": "t"})
    assert out["X-Api-Key"] == "***"
    assert out["user_ssn"] == "***"
    assert out["auth_token"] == "***"


def test_recurses_lists():
    out = redact({"events": [{"password": "x", "id": 3}]})
    assert out["events"][0]["password"] == "***"
    assert out["events"][0]["id"] == 3


def test_non_sensitive_untouched():
    assert redact({"name": "bob", "meta": {"count": 2}}) == {"name": "bob", "meta": {"count": 2}}
