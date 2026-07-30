from edgecache import cache_key


def test_reordered_query_hits_same_key():
    a = cache_key("https://Shop.Example.com/products?size=m&color=red")
    b = cache_key("https://shop.example.com/products?color=red&size=m")
    assert a == b


def test_ad_click_ids_do_not_fragment_the_cache():
    a = cache_key("https://shop.example.com/products?color=red&gclid=CjkKEQ1")
    b = cache_key("https://shop.example.com/products?color=red")
    assert a == b
