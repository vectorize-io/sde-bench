"""HARD-tier trap batch I for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). Categories (gen/categories.py):
  cachekey -> filter-rule  (sorted re-encoded params + tracking-drop set with utm_content carve-out
                            + empty-value drop + surgical case/slash normalization)
  featflag -> invariant    (per-flag crc32 hash input with a pinned separator + strict < boundary
                            + corp-users-in-beta-flags-only rule)

Hard-tier design goals as in batches A-H: multi-part policies (3+ interacting constraints),
bug reports in symptom vocabulary far from the decision wording, WIDE hidden tests (each policy
component pinned by its own small test function), and two naive guesses per trap, each passing
the repro but failing hidden.

Batch E/F/G/I lever ("buried decision"): each trap's conversation is a LONG (16-turn) meandering
design/debugging session. The policy parts surface piecewise, separated by legitimate same-module
filler (metrics budgets, rollout staging, CI flakiness), and at least one plausible alternative is
explicitly REJECTED mid-chat (the rejected alternative matches a naive fix). The full rule is
still unambiguously inferable from the chat alone.

featflag crc32 pins (verified with zlib.crc32 before authoring the tests):
  crc32("ana@example.com:new-checkout")%100 == 79   crc32("ana@example.com:new-nav")%100 == 1
  crc32("ben@example.com:search-v2")%100   == 67   crc32("eli@example.com:promo-banner")%100 == 32
  crc32("cody@example.com:dark-mode")%100  == 37   crc32("dev@corp.example:perf-cache")%100 == 73
  crc32("ana@example.com:beta-newui")%100  == 68
  no-separator naive: crc32("search-v2ben@example.com")%100 == 30 (in at 50, wrong side),
  crc32("promo-bannereli@example.com")%100 == 59 (out at 50, wrong side),
  crc32("fast-recouser-4821")%100 == 0 (leaks at percent=0 under <=).
"""


# --------------------------------------------------------------------------- cachekey
# Policy (all parts required): query params are sorted by name (STABLE - the value order of a
# repeated name is preserved) and re-encoded; tracking params are DROPPED: any param starting
# utm_ plus exactly {gclid, fbclid, msclkid} - EXCEPT utm_content, which is KEPT (it routes the
# A/B feature experience, per the marketing-eng agreement); params with an EMPTY value are
# dropped entirely (the empty-value rule wins even for utm_content); scheme+host are lowercased
# but the path keeps its case AND its trailing slash exactly as given (the origin is
# case-sensitive object storage; /dir/ and /dir are different resources).
# HEAD bug: the full URL string is used as-is - nothing sorted, nothing dropped.
# Naive (a): sorts + drops ALL utm_* (including utm_content) + the literal click-id set, but
# keeps empty-valued params. Naive (b): sorts + drops the exact policy set including the
# utm_content carve-out, but "aggressively normalizes" - lowercases the whole path and strips
# trailing slashes.

_CK_HEADER = ('"""Edge-cache key normalization."""\n\n'
              'from urllib.parse import parse_qsl, urlencode, urlsplit\n\n'
              '_CLICK_IDS = {"gclid", "fbclid", "msclkid"}\n\n\n')

_CK_KEEP = ('def _keep(name, value):\n'
            '    if value == "":\n'
            '        return False  # empty-valued params fragment the cache; the origin ignores them\n'
            '    if name in _CLICK_IDS:\n'
            '        return False\n'
            '    if name.startswith("utm_") and name != "utm_content":\n'
            '        return False\n'
            '    return True\n\n\n')

CACHEKEY = {
    "name": "cachekey",
    "marker": "marketing-eng",   # the answer-token used by the source-isolation check
    "category": "filter-rule",
    "pkg": "edgecache",
    "module": "edgecache/keys.py",
    "init": '"""edgecache package."""\nfrom .keys import cache_key\n\n__all__ = ["cache_key"]\n',
    "import_line": "from edgecache import cache_key",
    # HEAD bug: the raw URL string is the key - nothing sorted, nothing dropped
    "bug": ('"""Edge-cache key normalization."""\n\n\n'
            'def cache_key(url):\n'
            '    """Normalize a URL into an edge-cache key."""\n'
            '    return url.strip()\n'),
    "correct": (_CK_HEADER + _CK_KEEP +
                'def cache_key(url):\n'
                '    """Normalize a URL into an edge-cache key.\n'
                '\n'
                '    Cache-key policy (CDN working group):\n'
                '      - query params are sorted by name (STABLE: the value order of a\n'
                '        repeated name is preserved) and re-encoded canonically.\n'
                '      - tracking params are dropped: any utm_* param plus exactly\n'
                '        {gclid, fbclid, msclkid} - EXCEPT utm_content, which is KEPT\n'
                '        because it routes the A/B feature experience (the marketing-eng\n'
                '        agreement); dropping it serves the wrong variant from cache.\n'
                '      - params with an empty value are dropped entirely (this rule wins\n'
                '        even for utm_content).\n'
                '      - scheme and host are lowercased; the path keeps its case AND its\n'
                '        trailing slash exactly as given - the origin is case-sensitive\n'
                '        object storage, and /dir/ vs /dir are different resources.\n'
                '    """\n'
                '    parts = urlsplit(url)\n'
                '    params = [(n, v) for n, v in parse_qsl(parts.query, keep_blank_values=True)\n'
                '              if _keep(n, v)]\n'
                '    params.sort(key=lambda p: p[0])  # stable: repeated-name value order preserved\n'
                '    key = parts.scheme.lower() + "://" + parts.netloc.lower() + parts.path\n'
                '    if params:\n'
                '        key = key + "?" + urlencode(params)\n'
                '    return key\n'),
    "naive": [
        # sorts + drops ALL utm_* (including utm_content) + the click-id set, empty values kept
        (_CK_HEADER +
         'def cache_key(url):\n'
         '    """Normalize a URL into an edge-cache key (sorted params, tracking stripped)."""\n'
         '    parts = urlsplit(url)\n'
         '    params = [(n, v) for n, v in parse_qsl(parts.query, keep_blank_values=True)\n'
         '              if not (n.startswith("utm_") or n in _CLICK_IDS)]\n'
         '    params.sort(key=lambda p: p[0])\n'
         '    key = parts.scheme.lower() + "://" + parts.netloc.lower() + parts.path\n'
         '    if params:\n'
         '        key = key + "?" + urlencode(params)\n'
         '    return key\n'),
        # exact drop set with the utm_content carve-out, but aggressive normalization:
        # the whole path lowercased and trailing slashes stripped
        (_CK_HEADER + _CK_KEEP +
         'def cache_key(url):\n'
         '    """Normalize a URL into an edge-cache key (aggressively normalized)."""\n'
         '    parts = urlsplit(url)\n'
         '    params = [(n, v) for n, v in parse_qsl(parts.query, keep_blank_values=True)\n'
         '              if _keep(n, v)]\n'
         '    params.sort(key=lambda p: p[0])\n'
         '    path = parts.path.lower().rstrip("/")\n'
         '    key = parts.scheme.lower() + "://" + parts.netloc.lower() + path\n'
         '    if params:\n'
         '        key = key + "?" + urlencode(params)\n'
         '    return key\n'),
    ],
    "decision_subject": "fix: cache_key canonicalization - stable param sort, tracking-drop set with "
                        "the utm_content carve-out, empty-value drop, surgical case rules",
    "decision_rationale": (
        "Every cache symptom from the campaign launch traced to cache_key using the raw URL string. "
        "The policy: query params are sorted by name - a STABLE sort, so the value order of a "
        "repeated name is preserved - and re-encoded canonically. Tracking params are dropped: any "
        "param starting utm_ plus exactly gclid, fbclid and msclkid, nothing heuristic beyond that - "
        "EXCEPT utm_content, which is KEPT per the marketing-eng agreement because it routes the A/B "
        "feature experience; dropping it serves one variant's cached page to the other cohort. Params "
        "with an empty value are dropped entirely (that rule wins even for utm_content; the origin "
        "ignores them and they only fragment the cache). Normalization is surgical: scheme and host "
        "lowercase - DNS is case-insensitive - but the path keeps its case and its trailing slash "
        "exactly as given, because the origin is case-sensitive object storage and /dir/ vs /dir are "
        "different resources; collapsing either serves the wrong object."),
    "conversation": [
        {"role": "user", "text": "Since marketing launched the paid campaigns, the edge cache hit-rate graph fell off a cliff and the CDN invoice nearly doubled - origin egress is way up. On top of that, two customers filed tickets saying the product page they see doesn't match the experiment cohort our analytics says they're in. All of it smells like edgecache - can you look at cache_key in keys.py?"},
        {"role": "assistant", "text": "Found it fast: cache_key returns the URL string as-is. Every ad click appends gclid and a bag of utm_ params with unique values, so each click is a distinct key - that's the hit-rate cliff and the bill. My plan: parse the query, sort the params, drop everything that looks like tracking - all utm_* plus gclid, fbclid, msclkid - and while I'm at it normalize hard: lowercase the whole URL and strip trailing slashes so near-identical URLs collapse to one key."},
        {"role": "user", "text": "Sorting is right, and the drop list is close - but two corrections before you write code. The drop set is exact: every utm_ param EXCEPT utm_content, plus exactly gclid, fbclid and msclkid - no fuzzy 'looks like tracking' heuristics beyond those. utm_content stays in the key: that's a standing agreement with marketing-eng, because utm_content routes which A/B feature experience the page renders. Fold it into one key and the CDN serves variant A's page to the B cohort - which is exactly the misrouted-experiment tickets we just got."},
        {"role": "assistant", "text": "Got it - utm_content is load-bearing, everything else utm_ goes, plus those three click IDs and nothing more. Separate thing I noticed while in keys.py: we have zero visibility into what the normalizer actually drops. Want a log line per dropped param so we can audit the campaign traffic?"},
        {"role": "user", "text": "Not a log line - at edge volumes per-request logging would drown the collector; a counter tagged by param name is plenty, and only for the dropped ones. Also, unrelated heads-up: the purge-webhook test in the edgecache suite has been flaky on CI since Tuesday - infra says it's a sandbox timeout, not your problem - so rerun before you blame your change."},
        {"role": "assistant", "text": "Counter it is. Next question on the sort: plain lexicographic sort by param name, but what about a repeated name, like tag=b&tag=a - sort the values too so the key is maximally canonical?"},
        {"role": "user", "text": "No - sort by NAME only and keep it stable: within a repeated name the original value order is preserved. Some origin endpoints treat repeated-param order as meaningful, so tag=b&tag=a and tag=a&tag=b are legitimately different requests. Sort names, preserve value order, re-encode the result canonically - that's the whole sorting rule."},
        {"role": "assistant", "text": "Stable sort by name, re-encoded. What about params with an empty value - ref= or utm_content= with nothing after the equals? Keep them sorted in place, or normalize the value somehow?"},
        {"role": "user", "text": "Drop them entirely - an empty-valued param never reaches the origin's handler logic, it just fragments the cache. And yes, that rule wins even for utm_content: utm_content= with an empty value is dropped like anything else. Only a non-empty utm_content is part of the key."},
        {"role": "assistant", "text": "Empty means gone, carve-out or not. Now the normalization half - I proposed lowercasing the whole URL and stripping trailing slashes. Confirm that part and I'll start on the tests?"},
        {"role": "user", "text": "That part is off the table. Scheme and host lowercase, yes - DNS is case-insensitive and mixed-case hosts from the app router were splitting the cache. But the path is untouchable: the origin is case-sensitive object storage, /API/Docs and /api/docs are different objects, and we've had a live incident where slash-stripping made /reports/ - a directory index - collide with /reports the file. Path case preserved, trailing slash preserved, exactly as given."},
        {"role": "assistant", "text": "Surgical then: lowercase stops at the authority, the path is byte-preserved. Different topic - rollout. Changing the key function invalidates effectively the whole edge cache at deploy; do we need a warm-up plan or do we just eat the origin spike?"},
        {"role": "user", "text": "Staged: ship computing the new key alongside the old one for a day, compare hit-rates in shadow, then cut over region by region overnight - traffic troughs absorb the cold cache. That's ops' standard playbook, nothing for the code to do differently. One more edge while you're in there: what does your parse do with a fragment, like #section?"},
        {"role": "assistant", "text": "Fragments never leave the browser, so urlsplit already excludes them from the key path and query - the key is scheme://host + path + the re-encoded query. Speaking of which: when every param is dropped, do you want a bare trailing '?' kept in the key or removed?"},
        {"role": "user", "text": "Removed - if nothing survives the filter, the key is just scheme://host plus the path, no dangling question mark. A URL with only tracking params and the same URL with no query must land on the same cached object; that equivalence is half the hit-rate win."},
        {"role": "assistant", "text": "Understood - and with the raw-string key gone the dashboard's 'unique objects' count finally becomes honest too. Recap of cache_key(url): parse, then filter - drop every utm_ param EXCEPT utm_content (kept per the marketing-eng agreement, it routes the A/B experience), drop exactly gclid, fbclid, msclkid, and drop any param with an empty value (that rule wins even for utm_content). Sort the survivors by name with a STABLE sort - repeated-name value order preserved - and re-encode canonically. Lowercase scheme and host only; the path keeps its case and its trailing slash exactly as given (case-sensitive origin, /dir/ vs /dir are different resources). No query survivors means no '?' in the key."},
    ],
    "existing_test": (
        'from edgecache import cache_key\n\n\n'
        'def test_simple_url_roundtrip():\n'
        '    assert cache_key("https://api.example.com/v1/data") == "https://api.example.com/v1/data"\n\n\n'
        'def test_distinct_paths_distinct_keys():\n'
        '    assert cache_key("https://api.example.com/a") != cache_key("https://api.example.com/b")\n\n\n'
        'def test_query_matters():\n'
        '    assert cache_key("https://cdn.example.com/app.js?v=3") != cache_key("https://cdn.example.com/app.js")\n\n\n'
        'def test_deterministic():\n'
        '    u = "https://cdn.example.com/assets/app.js?v=3"\n'
        '    assert cache_key(u) == cache_key(u)\n'),
    # reordered params + a click id, on an all-lowercase no-trailing-slash path with no
    # utm_content and no empty values: every candidate policy collapses both pairs to one
    # key; only the HEAD bug (raw string) keeps them distinct.
    "repro_test": (
        'from edgecache import cache_key\n\n\n'
        'def test_reordered_query_hits_same_key():\n'
        '    a = cache_key("https://Shop.Example.com/products?size=m&color=red")\n'
        '    b = cache_key("https://shop.example.com/products?color=red&size=m")\n'
        '    assert a == b\n\n\n'
        'def test_ad_click_ids_do_not_fragment_the_cache():\n'
        '    a = cache_key("https://shop.example.com/products?color=red&gclid=CjkKEQ1")\n'
        '    b = cache_key("https://shop.example.com/products?color=red")\n'
        '    assert a == b\n'),
    "hidden_test": (
        'from edgecache import cache_key\n\n\n'
        'def test_canonical_form_sorted_host_lowered_path_preserved():\n'
        '    key = cache_key("https://Shop.Example.COM/Products/list?b=2&a=1&a=3")\n'
        '    assert key == "https://shop.example.com/Products/list?a=1&a=3&b=2"\n\n\n'
        'def test_utm_content_is_kept():\n'
        '    key = cache_key("https://shop.example.com/p?utm_content=variant-b&sku=9")\n'
        '    assert key == "https://shop.example.com/p?sku=9&utm_content=variant-b"\n\n\n'
        'def test_other_tracking_params_are_dropped():\n'
        '    a = cache_key("https://shop.example.com/p?utm_source=nl&utm_medium=email"\n'
        '                  "&gclid=g1&fbclid=f2&msclkid=m3&sku=9")\n'
        '    b = cache_key("https://shop.example.com/p?sku=9")\n'
        '    assert a == b\n\n\n'
        'def test_empty_valued_params_are_dropped():\n'
        '    b = cache_key("https://shop.example.com/p?sku=9")\n'
        '    assert cache_key("https://shop.example.com/p?sku=9&ref=") == b\n'
        '    assert cache_key("https://shop.example.com/p?sku=9&utm_content=") == b\n\n\n'
        'def test_trailing_slash_is_preserved():\n'
        '    assert cache_key("https://shop.example.com/docs/") != cache_key("https://shop.example.com/docs")\n\n\n'
        'def test_path_case_is_preserved():\n'
        '    assert cache_key("https://shop.example.com/API/Users") != cache_key("https://shop.example.com/api/users")\n\n\n'
        'def test_host_and_scheme_case_insensitive():\n'
        '    a = cache_key("HTTPS://CDN.Example.com/x?a=1")\n'
        '    b = cache_key("https://cdn.example.com/x?a=1")\n'
        '    assert a == b\n\n\n'
        'def test_repeated_name_value_order_preserved():\n'
        '    key = cache_key("https://shop.example.com/search?tag=b&tag=a&q=x")\n'
        '    assert key == "https://shop.example.com/search?q=x&tag=b&tag=a"\n\n\n'
        'def test_only_tracking_params_collapses_to_bare_path():\n'
        '    a = cache_key("https://shop.example.com/landing?utm_source=ad&gclid=g9")\n'
        '    b = cache_key("https://shop.example.com/landing")\n'
        '    assert a == b\n'),
    "bug_report": ("Since the ad campaign launched, the edge cache hit-rate has cratered and the CDN "
                   "bill nearly doubled - origin egress is spiking on pages that should be cached. "
                   "Separately, two customers report seeing someone else's experiment variant on "
                   "pages our analytics says belong to the other cohort. A failing repro is at "
                   "tests/test_regression.py. Fix cache_key so equivalent requests share a cache "
                   "entry, without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- featflag
# Policy (all parts required): the bucketing hash input is user_id + ":" + flag_name - per-flag
# independence with the colon separator pinned (analytics recomputes the same bytes; decided
# after the cross-flag correlation incident where users landed in every experiment at once);
# hash = crc32 of the utf-8 bytes, bucket = crc % 100; a user is IN when bucket < percent
# (strictly less: percent=0 nobody, percent=100 everybody); user ids ending @corp.example are
# ALWAYS in, but ONLY when the flag name starts with "beta-" (the internal-beta convention) -
# for any other flag corp users bucket normally.
# HEAD bug: hashes user_id alone (correlated across flags), uses <=, no corp rule.
# Naive (a): correct per-flag hash + < boundary, but corp users are always in for EVERY flag.
# Naive (b): per-flag hash + the corp-beta rule right, but the hash input is
# flag_name + user_id WITHOUT the separator (collision-prone; the hidden test pins exact crc
# buckets computed with the separator) and the boundary is <=.

_FF_HEADER = ('"""Percentage-rollout flag bucketing."""\n\n'
              'from zlib import crc32\n\n\n')

FEATFLAG = {
    "name": "featflag",
    "marker": "internal-beta",   # the answer-token used by the source-isolation check
    "category": "invariant",
    "pkg": "flagcore",
    "module": "flagcore/bucket.py",
    "init": '"""flagcore package."""\nfrom .bucket import bucket\n\n__all__ = ["bucket"]\n',
    "import_line": "from flagcore import bucket",
    # HEAD bug: hashes the user alone (every flag correlates), <= boundary, no corp rule
    "bug": (_FF_HEADER +
            'def bucket(user_id, flag_name, percent):\n'
            '    """Return True when the user falls inside the rollout percentage."""\n'
            '    return crc32(user_id.encode("utf-8")) % 100 <= percent\n'),
    "correct": (_FF_HEADER +
                'def bucket(user_id, flag_name, percent):\n'
                '    """Return True when the user falls inside the flag\'s rollout percentage.\n'
                '\n'
                '    Bucketing policy (flag-platform, post cross-flag correlation incident):\n'
                '      - the hash input is user_id + ":" + flag_name - per-flag independence,\n'
                '        with the colon separator pinned because analytics recomputes the\n'
                '        exact same bytes; concatenating without the separator collides.\n'
                '      - hash = crc32 of the utf-8 bytes; bucket = crc % 100.\n'
                '      - IN means bucket < percent, strictly: percent=0 nobody,\n'
                '        percent=100 everybody.\n'
                '      - user ids ending @corp.example are always in, but ONLY for flag\n'
                '        names starting with "beta-" (the internal-beta convention); for\n'
                '        every other flag corp users bucket normally.\n'
                '    """\n'
                '    if user_id.endswith("@corp.example") and flag_name.startswith("beta-"):\n'
                '        return True\n'
                '    b = crc32((user_id + ":" + flag_name).encode("utf-8")) % 100\n'
                '    return b < percent\n'),
    "naive": [
        # per-flag hash + strict boundary right, but corp users always in for EVERY flag
        (_FF_HEADER +
         'def bucket(user_id, flag_name, percent):\n'
         '    """Return True when the user falls inside the flag\'s rollout percentage."""\n'
         '    if user_id.endswith("@corp.example"):\n'
         '        return True\n'
         '    b = crc32((user_id + ":" + flag_name).encode("utf-8")) % 100\n'
         '    return b < percent\n'),
        # per-flag hash + corp-beta rule right, but the hash input drops the separator
        # (flag_name + user_id concatenated) and the boundary is <=
        (_FF_HEADER +
         'def bucket(user_id, flag_name, percent):\n'
         '    """Return True when the user falls inside the flag\'s rollout percentage."""\n'
         '    if user_id.endswith("@corp.example") and flag_name.startswith("beta-"):\n'
         '        return True\n'
         '    b = crc32((flag_name + user_id).encode("utf-8")) % 100\n'
         '    return b <= percent\n'),
    ],
    "decision_subject": "fix: bucket() per-flag hash input with the pinned separator, strict < "
                        "boundary, corp override only for beta- flags",
    "decision_rationale": (
        "All three flag symptoms traced to bucket() hashing the user id alone. The policy: the "
        "bucketing hash input is user_id + \":\" + flag_name - per-flag independence, adopted after "
        "the cross-flag correlation incident where the same accounts landed in every experiment at "
        "once - and the colon separator is pinned: analytics recomputes the identical crc32 over the "
        "identical bytes, and concatenating without the separator makes distinct (user, flag) pairs "
        "collide. The hash is crc32 of the utf-8 bytes and the bucket is crc % 100. A user is IN "
        "when bucket < percent, strictly - percent=0 enrolls nobody and percent=100 enrolls "
        "everybody; the old <= off-by-one is part of why rollout percentages never matched the "
        "analytics counts. User ids ending @corp.example are always in, but ONLY when the flag name "
        "starts with beta- (the internal-beta convention); for every other flag corp users bucket "
        "normally - a blanket corp override is exactly how an internal dashboard flag leaks to "
        "customer-visible surfaces."),
    "conversation": [
        {"role": "user", "text": "Three flag-platform complaints landed this week and I think they're one bug. Support says the same accounts end up in every experimental feature at once - a user who got the new checkout also got new nav, new search, all of it. An internal dashboard flag showed up for a real customer. And every rollout we run, the percentage we set never matches the enrolled count analytics reports. Can you dig into bucket() in flagcore?"},
        {"role": "assistant", "text": "Looked at it - bucket() hashes ONLY the user id: crc32(user_id) % 100, compared against percent. So a user's bucket number is identical for every flag; anyone under 30 is in every 30% experiment simultaneously. That's your correlated-cohorts complaint in one line. My plan: hash the user and the flag together so each flag gets an independent shuffle - I'll concatenate flag_name + user_id and crc32 that - and while I'm in there, force corp accounts into every flag so the team can dogfood."},
        {"role": "user", "text": "The direction is right but both details are wrong, and both wrongnesses have history. The hash input is pinned: user_id + \":\" + flag_name, colon separator, exactly that string. Analytics recomputes the same crc32 on their side to attribute events, so the bytes must match exactly - and plain concatenation without a separator is collision-prone anyway. This exact input string came out of the post-incident review after the cross-flag correlation mess, so treat it as an interface, not an implementation detail."},
        {"role": "assistant", "text": "user, colon, flag - crc32 over the utf-8 bytes, mod 100, and it's a contract with analytics. Noted. Unrelated while I'm in the file: assignments are completely silent today. Want me to log each bucketing decision so support can answer 'why did this user get the feature'?"},
        {"role": "user", "text": "Sampled metric, not logs - bucket() runs on every request and full logging would melt the collector; a counter by (flag, in/out) plus a debug endpoint that recomputes one user on demand covers the support case. Also heads-up: the flag-sync test in the flagcore suite has been flaky on CI all week - infra says timeout, not correctness - rerun before you suspect your change."},
        {"role": "assistant", "text": "Counter plus on-demand recompute, got it. Now the comparison: today it's bucket <= percent. Keep that convention and document it, or switch to strict less-than?"},
        {"role": "user", "text": "Strict less-than, and this one matters more than it looks: bucket < percent. With buckets 0..99, percent=0 must enroll NOBODY and percent=100 must enroll everybody. The current <= means percent=0 still enrolls the bucket-0 users - about 1% of traffic silently in every 'disabled' experiment - and it's a chunk of why our rollout numbers never reconcile with analytics."},
        {"role": "assistant", "text": "So < it is: 0 is truly off, 100 is truly on. Back to my corp idea then - forcing @corp.example accounts into every flag for dogfooding. You said it was wrong; what's the actual rule?"},
        {"role": "user", "text": "Scoped, not blanket. Corp accounts - user ids ending @corp.example - are always in ONLY when the flag name starts with beta-. That's the internal-beta convention: teams name dogfood flags beta-something and every corp employee sees them. For any other flag, corp users bucket exactly like customers - a blanket corp override is precisely how the internal dashboard flag leaked: it wasn't a beta- flag, someone force-included staff, and a shared demo account counted as staff."},
        {"role": "assistant", "text": "Understood - the override keys on BOTH ends: corp domain AND the beta- prefix, otherwise normal bucketing. Ordering question: does the corp check happen before or after the percent math? At percent=0 on beta-newui, is a corp user in or out?"},
        {"role": "user", "text": "In. The corp-beta override is absolute and evaluated first - a beta- flag at 0% still shows for every corp account; that's what makes 'create the flag at 0, dogfood internally, then ramp' work. The percent only governs the hashed population."},
        {"role": "assistant", "text": "Override first, hash second. Rollout logistics: changing the hash input reshuffles every existing cohort - users will flip in and out of running experiments at deploy. Do we need a migration, like keeping the old hash for flags created before the fix?"},
        {"role": "user", "text": "No dual-hash - we take the one-time churn. Running experiments restart their measurement window after the deploy; product signed off. A frozen legacy hash means carrying the correlated bug forever for old flags, which is worse. Ship it as one cutover."},
        {"role": "assistant", "text": "One cutover, no legacy path. Two edge validations while I write tests: percent arrives as an int 0..100 from the flag store - do I clamp or validate here? And any unicode concerns in user ids before crc32?"},
        {"role": "user", "text": "Neither belongs in bucket(): the flag store validates percent at write time, so assume 0..100 and don't clamp - a clamp would hide store bugs. And encode the input string as utf-8 before crc32, always - ids are ASCII today but the encode call is part of matching analytics byte-for-byte."},
        {"role": "assistant", "text": "No clamping, explicit utf-8 encode. Last check on determinism: no per-process salt, no time component - the same (user, flag, percent) triple must answer the same everywhere, or the debug endpoint and analytics reattribution both break. Confirmed?"},
        {"role": "user", "text": "Confirmed, fully deterministic. Recap it so we're aligned before the PR."},
        {"role": "assistant", "text": "Recap of bucket(user_id, flag_name, percent): first the override - user ids ending @corp.example are always in when and ONLY when the flag name starts with beta- (the internal-beta convention); every other flag buckets corp users normally. Otherwise hash user_id + \":\" + flag_name - the colon separator pinned, byte-for-byte the string analytics recomputes - as crc32 of the utf-8 bytes, bucket = crc % 100, and the user is in iff bucket < percent, strictly: percent=0 nobody, percent=100 everybody. No clamping, no salt, fully deterministic."},
    ],
    "existing_test": (
        'from flagcore import bucket\n\n\n'
        'def test_full_rollout_includes_everyone():\n'
        '    assert bucket("ana@example.com", "new-nav", 100) is True\n'
        '    assert bucket("ivan@mail.net", "new-checkout", 100) is True\n\n\n'
        'def test_deterministic():\n'
        '    assert bucket("jo@example.com", "search-v2", 50) == bucket("jo@example.com", "search-v2", 50)\n\n\n'
        'def test_returns_bool():\n'
        '    assert isinstance(bucket("kai@example.com", "dark-mode", 30), bool)\n'),
    # per-flag independence for one non-corp user at 50%: crc32("ana@example.com:new-checkout")%100
    # == 79 (out) while crc32("ana@example.com:new-nav")%100 == 1 (in) - and the no-separator
    # naive lands on the same booleans (98 -> out, 29 -> in); only the HEAD bug (user-only hash,
    # bucket 39 for both flags) answers the same for every flag.
    "repro_test": (
        'from flagcore import bucket\n\n\n'
        'def test_membership_is_independent_per_flag():\n'
        '    a = bucket("ana@example.com", "new-checkout", 50)\n'
        '    b = bucket("ana@example.com", "new-nav", 50)\n'
        '    assert a != b\n'
        '    assert b is True\n'),
    "hidden_test": (
        'from flagcore import bucket\n\n\n'
        'def test_hash_input_is_user_colon_flag():\n'
        '    # crc32(b"ben@example.com:search-v2") % 100 == 67 -> out at 50\n'
        '    assert bucket("ben@example.com", "search-v2", 50) is False\n'
        '    # crc32(b"eli@example.com:promo-banner") % 100 == 32 -> in at 50\n'
        '    assert bucket("eli@example.com", "promo-banner", 50) is True\n\n\n'
        'def test_boundary_is_strictly_less_than():\n'
        '    # crc32(b"cody@example.com:dark-mode") % 100 == 37\n'
        '    assert bucket("cody@example.com", "dark-mode", 37) is False\n'
        '    assert bucket("cody@example.com", "dark-mode", 38) is True\n\n\n'
        'def test_zero_percent_enrolls_nobody():\n'
        '    assert bucket("dana@mail.net", "perf-cache", 0) is False\n'
        '    assert bucket("user-4821", "fast-reco", 0) is False\n\n\n'
        'def test_hundred_percent_enrolls_everybody():\n'
        '    assert bucket("lena@mail.net", "new-nav", 100) is True\n'
        '    assert bucket("ana@example.com", "new-checkout", 100) is True\n\n\n'
        'def test_per_flag_independence():\n'
        '    # crc32(b"ana@example.com:new-checkout") % 100 == 79; ...:new-nav == 1\n'
        '    assert bucket("ana@example.com", "new-checkout", 50) is False\n'
        '    assert bucket("ana@example.com", "new-nav", 50) is True\n\n\n'
        'def test_corp_users_always_in_beta_flags():\n'
        '    assert bucket("dev@corp.example", "beta-newui", 0) is True\n'
        '    assert bucket("ops@corp.example", "beta-dashboard", 0) is True\n\n\n'
        'def test_corp_users_bucket_normally_on_other_flags():\n'
        '    assert bucket("dev@corp.example", "perf-cache", 0) is False\n'
        '    # crc32(b"dev@corp.example:perf-cache") % 100 == 73\n'
        '    assert bucket("dev@corp.example", "perf-cache", 73) is False\n'
        '    assert bucket("dev@corp.example", "perf-cache", 74) is True\n\n\n'
        'def test_non_corp_users_bucket_normally_on_beta_flags():\n'
        '    # crc32(b"ana@example.com:beta-newui") % 100 == 68\n'
        '    assert bucket("ana@example.com", "beta-newui", 68) is False\n'
        '    assert bucket("ana@example.com", "beta-newui", 69) is True\n'),
    "bug_report": ("Support says the same accounts get every experimental feature at once - a user "
                   "enrolled in one experiment is somehow enrolled in all of them. An internal "
                   "dashboard flag was visible to a real customer, and the rollout percentages we "
                   "configure never match the enrolled counts analytics reports. A failing repro is "
                   "at tests/test_regression.py. Fix bucket so rollout membership behaves as "
                   "configured, without breaking existing behaviour."),
}


TRAPS_HARD_I = {t["name"]: t for t in [CACHEKEY, FEATFLAG]}
