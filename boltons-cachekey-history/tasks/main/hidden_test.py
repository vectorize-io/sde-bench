from edgecache import cache_key


def test_canonical_form_sorted_host_lowered_path_preserved():
    key = cache_key("https://Shop.Example.COM/Products/list?b=2&a=1&a=3")
    assert key == "https://shop.example.com/Products/list?a=1&a=3&b=2"


def test_utm_content_is_kept():
    key = cache_key("https://shop.example.com/p?utm_content=variant-b&sku=9")
    assert key == "https://shop.example.com/p?sku=9&utm_content=variant-b"


def test_other_tracking_params_are_dropped():
    a = cache_key("https://shop.example.com/p?utm_source=nl&utm_medium=email"
                  "&gclid=g1&fbclid=f2&msclkid=m3&sku=9")
    b = cache_key("https://shop.example.com/p?sku=9")
    assert a == b


def test_empty_valued_params_are_dropped():
    b = cache_key("https://shop.example.com/p?sku=9")
    assert cache_key("https://shop.example.com/p?sku=9&ref=") == b
    assert cache_key("https://shop.example.com/p?sku=9&utm_content=") == b


def test_trailing_slash_is_preserved():
    assert cache_key("https://shop.example.com/docs/") != cache_key("https://shop.example.com/docs")


def test_path_case_is_preserved():
    assert cache_key("https://shop.example.com/API/Users") != cache_key("https://shop.example.com/api/users")


def test_host_and_scheme_case_insensitive():
    a = cache_key("HTTPS://CDN.Example.com/x?a=1")
    b = cache_key("https://cdn.example.com/x?a=1")
    assert a == b


def test_repeated_name_value_order_preserved():
    key = cache_key("https://shop.example.com/search?tag=b&tag=a&q=x")
    assert key == "https://shop.example.com/search?q=x&tag=b&tag=a"


def test_only_tracking_params_collapses_to_bare_path():
    a = cache_key("https://shop.example.com/landing?utm_source=ad&gclid=g9")
    b = cache_key("https://shop.example.com/landing")
    assert a == b
