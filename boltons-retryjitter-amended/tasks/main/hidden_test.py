from httpretry import should_retry, backoff_cap


def test_transient_4xx_retryable():
    assert should_retry(429, 1) is True
    assert should_retry(408, 1) is True


def test_permanent_4xx_not_retried():
    assert should_retry(400, 1) is False
    assert should_retry(401, 1) is False
    assert should_retry(403, 1) is False
    assert should_retry(404, 1) is False


def test_5xx_retryable():
    assert should_retry(500, 1) is True
    assert should_retry(503, 2) is True
    assert should_retry(599, 1) is True


def test_non_error_not_retried():
    assert should_retry(200, 1) is False
    assert should_retry(302, 1) is False


def test_attempt_budget():
    assert should_retry(503, 3) is True
    assert should_retry(503, 4) is False
    assert should_retry(429, 4) is False


def test_backoff_ceiling():
    assert backoff_cap() == 30
