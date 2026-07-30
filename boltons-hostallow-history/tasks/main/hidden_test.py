from egressgate import is_allowed


def test_exact_entries_match_case_insensitively():
    assert is_allowed("API.Corp.NET", ["api.corp.net"])
    assert is_allowed("api.corp.net", ["API.CORP.NET"])


def test_wildcard_matches_exactly_one_label():
    assert is_allowed("a.example.com", ["*.example.com"])
    assert not is_allowed("a.b.example.com", ["*.example.com"])


def test_wildcard_never_matches_the_bare_domain():
    assert not is_allowed("example.com", ["*.example.com"])
    assert is_allowed("example.com", ["example.com", "*.example.com"])


def test_wildcard_is_case_insensitive():
    assert is_allowed("Cdn.Example.COM", ["*.EXAMPLE.com"])


def test_lookalike_suffix_never_matches():
    assert not is_allowed("evilexample.com", ["example.com"])
    assert not is_allowed("aexample.com", ["*.example.com"])


def test_exact_entry_does_not_cover_subdomains():
    assert not is_allowed("sub.example.com", ["example.com"])


def test_ip_literals_match_only_exact_entries():
    assert is_allowed("10.0.0.5", ["10.0.0.5"])
    assert not is_allowed("10.0.0.5", ["*.0.0.5"])
    assert not is_allowed("192.168.1.20", ["*.168.1.20"])


def test_trailing_dot_fqdn_is_normalized():
    assert is_allowed("host.example.com.", ["host.example.com"])
    assert is_allowed("a.example.com.", ["*.example.com"])
    assert not is_allowed("a.b.example.com.", ["*.example.com"])
