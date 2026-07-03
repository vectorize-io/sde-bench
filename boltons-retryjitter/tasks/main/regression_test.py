from httpretry import should_retry


def test_auth_failure_not_retried():
    assert should_retry(401, 1) is False
    assert should_retry(503, 1) is True
