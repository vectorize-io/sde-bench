from egressgate import is_allowed


def test_lookalike_host_is_not_approved():
    allowlist = ["example.com", "*.example.com"]
    assert is_allowed("api.example.com", allowlist)
    assert not is_allowed("evilexample.com", allowlist)


def test_same_host_different_case_is_allowed():
    assert is_allowed("Payments.Corp.net", ["payments.corp.net"])
