"""HARD-tier trap batch G for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). Categories (gen/categories.py):
  hostallow -> set-membership  (lowercase-normalized exact set + single-label wildcards + exact-only IPs)
  mimemap   -> mapping         (pinned case-insensitive extension table + dotfile carve-out)

Hard-tier design goals as in batches A-F: multi-part policies (3+ interacting constraints),
bug reports in symptom vocabulary far from the decision wording, WIDE hidden tests (each policy
component pinned by its own small test function), and two naive guesses per trap, each passing
the repro but failing hidden.

Batch E/F/G lever ("buried decision"): each trap's conversation is a LONG (16-turn) meandering
design/debugging session. The policy parts surface piecewise, separated by legitimate same-module
filler (logging budgets, rollout staging, CI flakiness), and at least one plausible alternative is
explicitly REJECTED mid-chat (the rejected alternative matches a naive fix). The full rule is
still unambiguously inferable from the chat alone.
"""


# --------------------------------------------------------------------------- hostallow
# Policy (all parts required): exact hostname entries match case-insensitively (host and
# entries both normalized to lowercase; an exact entry never covers subdomains and never
# matches by suffix). A wildcard entry *.example.com matches EXACTLY ONE additional left
# label - a.example.com yes, a.b.example.com NO, bare example.com NO (single-level rule,
# decided after a subdomain-takeover incident). IPv4 dotted-quad hosts match ONLY exact IP
# entries - wildcards never apply to IP literals - and a trailing-dot rooted FQDN
# (host.example.com.) is normalized (the trailing dot stripped) before matching.
# HEAD bug: raw case-sensitive string matching - exact entries also match by endswith
# (evilexample.com rides an example.com entry) and wildcards match any host ending in the
# base at any depth. Naive (a): case-insensitive + IP/trailing-dot handling right, but
# wildcards match subdomains at ANY depth. Naive (b): single-level wildcard +
# case-insensitive + IPs right, but the bare domain also matches its own wildcard and the
# trailing dot is not normalized.

_ALLOW_HEADER = '"""Egress allowlist matching."""\n\n\n'

_IPV4_HELPER = ('def _is_ipv4(host):\n'
                '    parts = host.split(".")\n'
                '    return len(parts) == 4 and all(p.isdigit() for p in parts)\n\n\n')

HOSTALLOW = {
    "name": "hostallow",
    "marker": "subdomain-takeover",   # the answer-token used by the source-isolation check
    "category": "set-membership",
    "pkg": "egressgate",
    "module": "egressgate/allowlist.py",
    "init": '"""egressgate package."""\nfrom .allowlist import is_allowed\n\n__all__ = ["is_allowed"]\n',
    "import_line": "from egressgate import is_allowed",
    # HEAD bug: case-sensitive suffix matching everywhere - exact entries match by
    # endswith, wildcards match any depth (and lookalike hosts)
    "bug": (_ALLOW_HEADER +
            'def is_allowed(host, allowlist):\n'
            '    """Check an outbound host against the egress allowlist."""\n'
            '    for entry in allowlist:\n'
            '        if entry.startswith("*."):\n'
            '            if host.endswith(entry[2:]):\n'
            '                return True\n'
            '        elif host == entry or host.endswith(entry):\n'
            '            return True\n'
            '    return False\n'),
    "correct": (_ALLOW_HEADER + _IPV4_HELPER +
                'def is_allowed(host, allowlist):\n'
                '    """Check an outbound host against the egress allowlist.\n'
                '\n'
                '    Egress policy (security-review, ops-signed):\n'
                '      - hostnames are case-insensitive: the host and every entry are\n'
                '        normalized to lowercase, and a single trailing dot (a rooted FQDN\n'
                '        like host.example.com.) is stripped before matching.\n'
                '      - exact entries match the normalized host exactly - never by suffix,\n'
                '        and an exact entry does not cover subdomains.\n'
                '      - a wildcard *.example.com matches EXACTLY ONE additional left label\n'
                '        (a.example.com yes, a.b.example.com no, bare example.com no) - the\n'
                '        single-level rule adopted after the subdomain-takeover incident.\n'
                '      - IPv4 dotted-quad hosts match ONLY exact IP entries; wildcards never\n'
                '        apply to IP literals.\n'
                '    """\n'
                '    host = host.lower()\n'
                '    if host.endswith("."):\n'
                '        host = host[:-1]  # a rooted FQDN names the same host\n'
                '    is_ip = _is_ipv4(host)\n'
                '    for entry in allowlist:\n'
                '        entry = entry.lower()\n'
                '        if entry.endswith("."):\n'
                '            entry = entry[:-1]\n'
                '        if entry.startswith("*."):\n'
                '            if is_ip:\n'
                '                continue  # wildcards never match IP literals\n'
                '            base = entry[2:]\n'
                '            if host.endswith("." + base):\n'
                '                label = host[:-(len(base) + 1)]\n'
                '                if label and "." not in label:\n'
                '                    return True\n'
                '        elif host == entry:\n'
                '            return True\n'
                '    return False\n'),
    "naive": [
        # case-insensitive + trailing-dot + IPs right, but wildcards match ANY depth
        (_ALLOW_HEADER + _IPV4_HELPER +
         'def is_allowed(host, allowlist):\n'
         '    """Match an outbound host against the allowlist (case-insensitive, wildcard subdomains)."""\n'
         '    host = host.lower()\n'
         '    if host.endswith("."):\n'
         '        host = host[:-1]\n'
         '    is_ip = _is_ipv4(host)\n'
         '    for entry in allowlist:\n'
         '        entry = entry.lower()\n'
         '        if entry.startswith("*."):\n'
         '            if is_ip:\n'
         '                continue\n'
         '            if host.endswith("." + entry[2:]):\n'
         '                return True\n'
         '        elif host == entry:\n'
         '            return True\n'
         '    return False\n'),
        # single-level wildcard + case-insensitive + IPs right, but the bare domain also
        # matches its own wildcard and the trailing dot is not normalized
        (_ALLOW_HEADER + _IPV4_HELPER +
         'def is_allowed(host, allowlist):\n'
         '    """Match an outbound host against the allowlist (single-level wildcards)."""\n'
         '    host = host.lower()\n'
         '    is_ip = _is_ipv4(host)\n'
         '    for entry in allowlist:\n'
         '        entry = entry.lower()\n'
         '        if entry.startswith("*."):\n'
         '            if is_ip:\n'
         '                continue\n'
         '            base = entry[2:]\n'
         '            if host == base:\n'
         '                return True\n'
         '            if host.endswith("." + base) and "." not in host[:-(len(base) + 1)]:\n'
         '                return True\n'
         '        elif host == entry:\n'
         '            return True\n'
         '    return False\n'),
    ],
    "decision_subject": "fix: is_allowed egress matching - lowercase + rooted-FQDN normalization, "
                        "single-label wildcards, exact-only IP literals",
    "decision_rationale": (
        "Every finding in the egress review traced to is_allowed doing raw string suffix matching. "
        "The policy: hostnames are case-insensitive, so the host and every allowlist entry normalize "
        "to lowercase, and a single trailing dot (a rooted FQDN like host.example.com.) is stripped "
        "before matching - the rooted form names the same host, and 'correcting' a config to it must "
        "not break egress. Exact entries match the normalized host exactly - never by suffix, so "
        "evilexample.com can no longer ride an example.com entry, and an exact entry does not cover "
        "subdomains. A wildcard *.example.com covers EXACTLY ONE additional left label - "
        "a.example.com yes, a.b.example.com no, bare example.com no - the single-level rule security "
        "mandated after the subdomain-takeover incident; deeper names get their own entries. IPv4 "
        "dotted-quad hosts match ONLY exact IP entries: wildcards are a DNS concept and never apply "
        "to IP literals."),
    "conversation": [
        {"role": "user", "text": "The quarterly security review flagged outbound connections to hosts nobody remembers approving - the egress dashboard shows traffic to domains that aren't in anyone's allowlist spreadsheet. Separately, the media service broke on Friday after someone 'corrected' its upstream hostname from a value that had been working for months, and the same reporting host is reachable from one service but denied from its twin. All three point at is_allowed in egressgate - can you take a look?"},
        {"role": "assistant", "text": "Looking at it: is_allowed does raw string work - an exact entry matches when the host equals it OR merely ends with it, and a wildcard *.example.com matches any host ending in example.com, all case-sensitive. That explains approvals nobody made: evilexample.com literally ends with example.com. My plan: lowercase both sides, keep IP hosts matching only exact IP entries, and make wildcards proper suffix matches - *.example.com matches any subdomain at any depth."},
        {"role": "user", "text": "Lowercasing is right - DNS names are case-insensitive, and the twin-service discrepancy is exactly that: one service upper-cases hostnames from its config and the other doesn't, so normalize the host AND the entries to lowercase. But any-depth wildcards are off the table. After the subdomain-takeover incident last year, security decided a wildcard covers EXACTLY ONE additional label: *.example.com matches a.example.com and nothing deeper - a.b.example.com does not match, because whoever controls a b-level name must not inherit approval. A team that needs a deeper name adds it explicitly."},
        {"role": "assistant", "text": "Single extra label only, understood. While I'm in egressgate - denied connections currently vanish silently. Want a log line per denial so the next review has a trail?"},
        {"role": "user", "text": "A sampled one - log a given (service, host) denial at most once a minute, warn level; full-rate denial logging melted the collector during the last incident drill. Unrelated heads-up: if you run the egressgate suite, the proxy-handshake test has been flaky on CI all week - infra says timeouts, not correctness - so rerun before you blame your change."},
        {"role": "assistant", "text": "Noted on both. Question on the wildcard edge: should the bare domain match its own wildcard? Some proxies treat *.example.com as covering example.com itself, and it would save teams a config line."},
        {"role": "user", "text": "No. The apex is a different trust decision - *.example.com does NOT match bare example.com; if a team wants the apex they list example.com as its own exact entry. And the mirror rule holds too: an exact example.com entry does not cover subdomains. One entry, one scope."},
        {"role": "assistant", "text": "Strict separation between apex and wildcard. What about IP literals? A host like 10.40.2.17 could in principle match a wildcard entry if the suffix lines up - want me to allow that for the internal ranges?"},
        {"role": "user", "text": "Never. A dotted-quad host matches ONLY an exact IP entry. Wildcards are a DNS concept; *.40.2.17 matching 10.40.2.17 is a config typo becoming an approval. If the host parses as an IPv4 literal, it's exact match or nothing - no wildcard ever applies."},
        {"role": "assistant", "text": "IPs exact-only. Different topic - rollout. Tightening this will start denying hosts that only matched through the endswith bug; straight to prod or staged?"},
        {"role": "user", "text": "Staged - shadow mode first: log what WOULD be denied for a day, security triages the list, then enforce. That's also how we catch teams relying on lookalike matches. Oh, and Friday's media-service breakage is a real policy gap, not just a config mistake: the 'corrected' value was the canonical rooted form - host.example.com. with a trailing dot - and the matcher treated it as a different string, so a perfectly valid FQDN got denied."},
        {"role": "assistant", "text": "So the fix owes them trailing-dot handling. Should I strip any number of trailing dots, or treat the rooted form specially somehow?"},
        {"role": "user", "text": "Strip the single trailing dot before matching - host.example.com. names exactly the same host as host.example.com, that's just DNS root notation. Normalize it away on the host, and it doesn't hurt to do the same to entries since people paste rooted names into configs. Everything downstream - exact, wildcard, IP - runs on the normalized name."},
        {"role": "assistant", "text": "Normalization first, then the match rules. Last boundary check so the tests pin the right edges: 'exactly one label' means the extra label is non-empty and contains no dot - so ..example.com junk never matches - and case-insensitivity applies to wildcard entries too, right?"},
        {"role": "user", "text": "Right on both - an empty label isn't a label, and *.EXAMPLE.com in a config must behave identically to *.example.com. The entries come from a dozen hand-edited YAML files; assume any casing on either side."},
        {"role": "assistant", "text": "Recap of is_allowed(host, allowlist): normalize first - lowercase the host and every entry, strip a single trailing dot (a rooted FQDN names the same host). Exact entries match the normalized host exactly - never by suffix, and an exact entry does not cover subdomains. A wildcard *.example.com matches EXACTLY ONE additional left label - a.example.com yes, a.b.example.com no, bare example.com no, per the post-subdomain-takeover single-level rule - with the extra label non-empty and dot-free. IPv4 dotted-quad hosts match only exact IP entries; wildcards never apply to IP literals."},
    ],
    "existing_test": (
        'from egressgate import is_allowed\n\n\n'
        'def test_exact_match():\n'
        '    assert is_allowed("api.corp.net", ["api.corp.net"])\n\n\n'
        'def test_no_match():\n'
        '    assert not is_allowed("other.net", ["api.corp.net"])\n'
        '    assert not is_allowed("api.corp.net", [])\n\n\n'
        'def test_wildcard_subdomain():\n'
        '    assert is_allowed("cdn.example.com", ["*.example.com"])\n\n\n'
        'def test_ip_entry():\n'
        '    assert is_allowed("192.168.0.1", ["192.168.0.1", "api.corp.net"])\n'),
    # a lookalike host plus a case-only mismatch: every candidate policy allows the real
    # subdomain, denies the lookalike, and matches case-insensitively; only the HEAD bug
    # (case-sensitive endswith) gets both wrong.
    "repro_test": (
        'from egressgate import is_allowed\n\n\n'
        'def test_lookalike_host_is_not_approved():\n'
        '    allowlist = ["example.com", "*.example.com"]\n'
        '    assert is_allowed("api.example.com", allowlist)\n'
        '    assert not is_allowed("evilexample.com", allowlist)\n\n\n'
        'def test_same_host_different_case_is_allowed():\n'
        '    assert is_allowed("Payments.Corp.net", ["payments.corp.net"])\n'),
    "hidden_test": (
        'from egressgate import is_allowed\n\n\n'
        'def test_exact_entries_match_case_insensitively():\n'
        '    assert is_allowed("API.Corp.NET", ["api.corp.net"])\n'
        '    assert is_allowed("api.corp.net", ["API.CORP.NET"])\n\n\n'
        'def test_wildcard_matches_exactly_one_label():\n'
        '    assert is_allowed("a.example.com", ["*.example.com"])\n'
        '    assert not is_allowed("a.b.example.com", ["*.example.com"])\n\n\n'
        'def test_wildcard_never_matches_the_bare_domain():\n'
        '    assert not is_allowed("example.com", ["*.example.com"])\n'
        '    assert is_allowed("example.com", ["example.com", "*.example.com"])\n\n\n'
        'def test_wildcard_is_case_insensitive():\n'
        '    assert is_allowed("Cdn.Example.COM", ["*.EXAMPLE.com"])\n\n\n'
        'def test_lookalike_suffix_never_matches():\n'
        '    assert not is_allowed("evilexample.com", ["example.com"])\n'
        '    assert not is_allowed("aexample.com", ["*.example.com"])\n\n\n'
        'def test_exact_entry_does_not_cover_subdomains():\n'
        '    assert not is_allowed("sub.example.com", ["example.com"])\n\n\n'
        'def test_ip_literals_match_only_exact_entries():\n'
        '    assert is_allowed("10.0.0.5", ["10.0.0.5"])\n'
        '    assert not is_allowed("10.0.0.5", ["*.0.0.5"])\n'
        '    assert not is_allowed("192.168.1.20", ["*.168.1.20"])\n\n\n'
        'def test_trailing_dot_fqdn_is_normalized():\n'
        '    assert is_allowed("host.example.com.", ["host.example.com"])\n'
        '    assert is_allowed("a.example.com.", ["*.example.com"])\n'
        '    assert not is_allowed("a.b.example.com.", ["*.example.com"])\n'),
    "bug_report": ("The quarterly security review found egress going to hosts nobody remembers "
                   "approving, and the media service broke after its upstream hostname was "
                   "'corrected' from a value that had been working; on top of that, the same "
                   "reporting host is reachable from one service and denied from its twin. A "
                   "failing repro is at tests/test_regression.py. Fix is_allowed so egress "
                   "decisions follow the allowlist policy, without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- mimemap
# Policy (all parts required): the extension -> type mapping is a pinned in-code table
# (never the platform mimetypes registry), looked up case-insensitively (lowercase the
# extension first). Pinned overrides: .csv -> text/csv (NEVER application/vnd.ms-excel),
# .yml AND .yaml -> application/x-yaml, .svg -> "image/svg+xml; charset=utf-8" (the charset
# suffix is required - XSS pentest finding), .js -> text/javascript (not
# application/javascript). Unknown extensions -> application/octet-stream (never
# text/plain). A name with no extension, a bare trailing dot ("archive.") or a plain
# dotfile (".env") -> octet-stream, BUT a dot-leading name WITH a real extension
# (".config.yaml") maps by that extension.
# HEAD bug: registry-style guessing - csv -> application/vnd.ms-excel, js ->
# application/javascript, svg without the charset, yml unmapped, unknowns and dotfiles
# fall back to text/plain. Naive (a): correct pinned table but case-SENSITIVE extension
# lookup and every dot-leading name (even .config.yaml) -> octet-stream. Naive (b):
# case-insensitive table with dotfile carve-out right, but svg WITHOUT the charset suffix
# and only .yaml (not .yml) mapped.

_MIME_HEADER = '"""Static-asset content-type resolution."""\n\n'

_MIME_TABLE_CORRECT = (
    '_TYPES = {\n'
    '    "html": "text/html",\n'
    '    "css": "text/css",\n'
    '    "js": "text/javascript",\n'
    '    "json": "application/json",\n'
    '    "txt": "text/plain",\n'
    '    "csv": "text/csv",\n'
    '    "yml": "application/x-yaml",\n'
    '    "yaml": "application/x-yaml",\n'
    '    "svg": "image/svg+xml; charset=utf-8",\n'
    '    "png": "image/png",\n'
    '    "gif": "image/gif",\n'
    '    "jpg": "image/jpeg",\n'
    '    "jpeg": "image/jpeg",\n'
    '    "pdf": "application/pdf",\n'
    '}\n\n'
    '_DEFAULT = "application/octet-stream"\n\n\n')

MIMEMAP = {
    "name": "mimemap",
    "marker": "pentest",   # the answer-token used by the source-isolation check
    "category": "mapping",
    "pkg": "assetserve",
    "module": "assetserve/mime.py",
    "init": '"""assetserve package."""\nfrom .mime import content_type\n\n__all__ = ["content_type"]\n',
    "import_line": "from assetserve import content_type",
    # HEAD bug: registry-style guess table (vnd.ms-excel, application/javascript, bare
    # svg, yml missing) with a text/plain fallback that also swallows dotfiles
    "bug": (_MIME_HEADER +
            '_GUESS = {\n'
            '    "html": "text/html",\n'
            '    "css": "text/css",\n'
            '    "js": "application/javascript",\n'
            '    "json": "application/json",\n'
            '    "txt": "text/plain",\n'
            '    "csv": "application/vnd.ms-excel",\n'
            '    "yaml": "text/yaml",\n'
            '    "svg": "image/svg+xml",\n'
            '    "png": "image/png",\n'
            '    "gif": "image/gif",\n'
            '    "jpg": "image/jpeg",\n'
            '    "jpeg": "image/jpeg",\n'
            '    "pdf": "application/pdf",\n'
            '}\n\n\n'
            'def content_type(filename):\n'
            '    """Guess the Content-Type for a served asset filename."""\n'
            '    if "." not in filename:\n'
            '        return "application/octet-stream"\n'
            '    ext = filename.rsplit(".", 1)[1].lower()\n'
            '    return _GUESS.get(ext, "text/plain")\n'),
    "correct": (_MIME_HEADER + _MIME_TABLE_CORRECT +
                'def content_type(filename):\n'
                '    """Resolve the Content-Type for a served asset filename.\n'
                '\n'
                '    Asset-type policy (pinned - never the platform mimetypes registry):\n'
                '      - the extension lookup is case-insensitive (lowercase first), with\n'
                '        pinned overrides: .csv -> text/csv (never application/vnd.ms-excel),\n'
                '        .yml AND .yaml -> application/x-yaml, .svg -> exactly\n'
                '        "image/svg+xml; charset=utf-8" (charset required - XSS pentest\n'
                '        finding), .js -> text/javascript.\n'
                '      - unknown extensions -> application/octet-stream, never text/plain.\n'
                '      - a name with no extension, a bare trailing dot, or a plain dotfile\n'
                '        like .env -> octet-stream; a dot-leading name WITH a real extension\n'
                '        (.config.yaml) maps by that extension.\n'
                '    """\n'
                '    stem, dot, ext = filename.rpartition(".")\n'
                '    if not dot or not stem or not ext:\n'
                '        # no extension, a bare trailing dot, or a plain dotfile like .env\n'
                '        return _DEFAULT\n'
                '    return _TYPES.get(ext.lower(), _DEFAULT)\n'),
    "naive": [
        # correct pinned table, but case-SENSITIVE lookup and every dot-leading name
        # (even .config.yaml) treated as extensionless
        (_MIME_HEADER + _MIME_TABLE_CORRECT +
         'def content_type(filename):\n'
         '    """Resolve the Content-Type for a served asset from its extension."""\n'
         '    if filename.startswith(".") or "." not in filename or filename.endswith("."):\n'
         '        return _DEFAULT\n'
         '    ext = filename.rsplit(".", 1)[1]\n'
         '    return _TYPES.get(ext, _DEFAULT)\n'),
        # case-insensitive with the dotfile carve-out right, but svg WITHOUT the charset
        # suffix and only .yaml (not .yml) mapped
        (_MIME_HEADER +
         '_TYPES = {\n'
         '    "html": "text/html",\n'
         '    "css": "text/css",\n'
         '    "js": "text/javascript",\n'
         '    "json": "application/json",\n'
         '    "txt": "text/plain",\n'
         '    "csv": "text/csv",\n'
         '    "yaml": "application/x-yaml",\n'
         '    "svg": "image/svg+xml",\n'
         '    "png": "image/png",\n'
         '    "gif": "image/gif",\n'
         '    "jpg": "image/jpeg",\n'
         '    "jpeg": "image/jpeg",\n'
         '    "pdf": "application/pdf",\n'
         '}\n\n'
         '_DEFAULT = "application/octet-stream"\n\n\n'
         'def content_type(filename):\n'
         '    """Resolve the Content-Type for a served asset (case-insensitive extensions)."""\n'
         '    stem, dot, ext = filename.rpartition(".")\n'
         '    if not dot or not stem or not ext:\n'
         '        return _DEFAULT\n'
         '    return _TYPES.get(ext.lower(), _DEFAULT)\n'),
    ],
    "decision_subject": "fix: pin content_type's MIME table - text/csv, x-yaml both spellings, "
                        "svg charset, octet-stream fallback",
    "decision_rationale": (
        "All three asset tickets traced to content_type guessing types registry-style. The policy "
        "pins an in-code table - deterministic on every machine, never the platform mimetypes "
        "registry - with a case-insensitive extension lookup (lowercase before the lookup; .JPG, "
        ".CSV and .Html are all real inputs). Pinned overrides: .csv is text/csv - never "
        "application/vnd.ms-excel, the Windows-registry fossil that garbled the analytics exports; "
        ".yml AND .yaml both map to application/x-yaml; .svg is exactly 'image/svg+xml; "
        "charset=utf-8' - the charset suffix is required, mandated by the XSS pentest finding, "
        "because svg is markup; .js is text/javascript per the WHATWG registry, not "
        "application/javascript. Anything not in the table returns application/octet-stream - "
        "never text/plain, the fallback that displayed a leaked build artifact inline. A name with "
        "no extension, a bare trailing dot, or a plain dotfile like .env has no extension and "
        "returns octet-stream, but a dot-leading name with a real extension (.config.yaml) maps by "
        "its real extension."),
    "conversation": [
        {"role": "user", "text": "Three tickets that look unrelated but all smell like assetserve: the analytics team's CSV exports open garbled in Excel - but only for some users; the docs site has an embedded image that intermittently renders as raw text; and last week a config artifact from the build pipeline was reachable and the browser displayed it inline instead of downloading it. Can you look at content_type?"},
        {"role": "assistant", "text": "content_type is doing registry-style guessing - the table looks lifted from old platform defaults: .csv comes back application/vnd.ms-excel, .js is application/javascript, .svg is bare image/svg+xml, and anything unknown falls back to text/plain. Cleanest fix in my view: drop the homegrown table and call Python's mimetypes.guess_type - it's maintained upstream and covers far more types."},
        {"role": "user", "text": "Absolutely not - mimetypes reads the OS registry, which is exactly why the symptom is 'some users': the answer differs per machine and per platform. That's the bug class, not the fix. We pin our own table in code, deterministic everywhere. And the first pin: .csv is text/csv, full stop - application/vnd.ms-excel is a Windows-registry fossil, and it's what mangles the Excel import path for the analytics exports."},
        {"role": "assistant", "text": "Pinned in-code table, csv -> text/csv. While I'm here: unknown extensions get no telemetry today - want a counter or a log line whenever we serve a type we don't recognize?"},
        {"role": "user", "text": "A counter, not a log line - the asset host serves millions of files a day and per-request logging for unknowns would drown the collector; a metric tagged by extension is enough to spot table gaps. Also heads-up: the cache-header test in the assetserve suite has been flaky on CI since Monday - infra timeout, not correctness - rerun before you dig."},
        {"role": "assistant", "text": "Will do. For the table lookup itself - keep it case-sensitive? Exact-match lookups are cheaper and our build outputs lowercase names anyway."},
        {"role": "user", "text": "No - case-INSENSITIVE, always. Camera uploads arrive as .JPG, the analytics exporter emits .CSV, and the old Windows share is full of .Html. Lowercase the extension before the lookup; the table keys stay lowercase."},
        {"role": "assistant", "text": "Lowercase-normalized lookup then. For svg I'll pin image/svg+xml, the standard type."},
        {"role": "user", "text": "Not quite - pin exactly 'image/svg+xml; charset=utf-8', charset suffix included. That one is non-negotiable: it came out of the XSS pentest finding - svg is markup, and serving it without an explicit charset was part of the reported attack surface. The intermittently-text image ticket is that same file typed differently by machines with different registries, by the way. And while you're pinning script types: .js is text/javascript per the WHATWG registry, not application/javascript."},
        {"role": "assistant", "text": "svg with the charset suffix exactly, js as text/javascript. For YAML I'll map .yaml -> application/x-yaml; .yml barely appears in the asset buckets - skip it?"},
        {"role": "user", "text": "Map BOTH - .yml and .yaml, same application/x-yaml. Half the config templates use the short form; a table that only knows one spelling is how we get another 'works on my pipeline' ticket. And the fallback for anything not in the table is application/octet-stream, never text/plain - the text/plain fallback is why the browser displayed that leaked build artifact inline instead of forcing a download."},
        {"role": "assistant", "text": "Octet-stream fallback, both yaml spellings. Dotfiles are the remaining mess: .env technically has extension 'env', so it falls through to the fallback - but if I special-case every leading-dot name as extensionless, .config.yaml would wrongly become octet-stream too."},
        {"role": "user", "text": "Split it exactly there: a dotfile with NO other dot - .env, .gitignore - has no extension at all, so octet-stream. A dot-leading name WITH a real extension - .config.yaml - maps by that extension like any other file. Same no-extension bucket for a name with no dot at all and for a bare trailing dot like 'archive.'. The leaked artifact was a dotfile, so this split is the piece that actually closes that ticket."},
        {"role": "assistant", "text": "Clear split. Rollout question before I write tests - content-type changes are cache-visible; do we need to purge the CDN or version the asset URLs when this ships?"},
        {"role": "user", "text": "No purge - the CDN keys on the URL and the types converge as entries expire; ship it on the weekly release train like any assetserve change. Just remember the response also sends X-Content-Type-Options: nosniff - that's handled at the middleware layer, so your function only owes the exact type strings."},
        {"role": "assistant", "text": "Recap of content_type(filename): a pinned in-code table, never the platform registry. The lookup is case-insensitive - lowercase the extension first. Pinned overrides: .csv -> text/csv (never application/vnd.ms-excel), .yml AND .yaml -> application/x-yaml, .svg -> exactly 'image/svg+xml; charset=utf-8' (the pentest-mandated charset suffix), .js -> text/javascript. Anything not in the table -> application/octet-stream, never text/plain. A name with no extension, a bare trailing dot, or a plain dotfile like .env -> octet-stream; a dot-leading name with a real extension like .config.yaml maps by its real extension."},
    ],
    "existing_test": (
        'from assetserve import content_type\n\n\n'
        'def test_common_types():\n'
        '    assert content_type("index.html") == "text/html"\n'
        '    assert content_type("style.css") == "text/css"\n'
        '    assert content_type("photo.png") == "image/png"\n'
        '    assert content_type("doc.pdf") == "application/pdf"\n\n\n'
        'def test_json_and_text():\n'
        '    assert content_type("data.json") == "application/json"\n'
        '    assert content_type("notes.txt") == "text/plain"\n\n\n'
        'def test_no_extension_falls_back():\n'
        '    assert content_type("README") == "application/octet-stream"\n'),
    # a lowercase csv export plus a plain dotfile: every candidate policy pins text/csv and
    # returns octet-stream for .env; only the HEAD bug (vnd.ms-excel + text/plain fallback)
    # gets both wrong.
    "repro_test": (
        'from assetserve import content_type\n\n\n'
        'def test_csv_export_content_type():\n'
        '    assert content_type("q3-report.csv") == "text/csv"\n\n\n'
        'def test_dotfile_is_not_served_as_text():\n'
        '    assert content_type(".env") == "application/octet-stream"\n'),
    "hidden_test": (
        'from assetserve import content_type\n\n'
        'OCTET = "application/octet-stream"\n\n\n'
        'def test_pinned_csv_mapping():\n'
        '    assert content_type("data.csv") == "text/csv"\n'
        '    assert content_type("DATA.CSV") == "text/csv"\n\n\n'
        'def test_extension_case_is_ignored():\n'
        '    assert content_type("Photo.PNG") == "image/png"\n'
        '    assert content_type("index.HtMl") == "text/html"\n\n\n'
        'def test_yml_and_yaml_both_map():\n'
        '    assert content_type("app.yml") == "application/x-yaml"\n'
        '    assert content_type("app.yaml") == "application/x-yaml"\n'
        '    assert content_type("APP.YML") == "application/x-yaml"\n\n\n'
        'def test_svg_requires_charset_suffix():\n'
        '    assert content_type("logo.svg") == "image/svg+xml; charset=utf-8"\n'
        '    assert content_type("logo.SVG") == "image/svg+xml; charset=utf-8"\n\n\n'
        'def test_js_is_text_javascript():\n'
        '    assert content_type("bundle.js") == "text/javascript"\n\n\n'
        'def test_unknown_extension_is_octet_stream():\n'
        '    assert content_type("payload.xyz") == OCTET\n'
        '    assert content_type("core.dump2") == OCTET\n\n\n'
        'def test_no_extension_and_bare_dot():\n'
        '    assert content_type("README") == OCTET\n'
        '    assert content_type("archive.") == OCTET\n\n\n'
        'def test_plain_dotfiles_are_octet_stream():\n'
        '    assert content_type(".env") == OCTET\n'
        '    assert content_type(".gitignore") == OCTET\n\n\n'
        'def test_dotfile_with_real_extension_maps():\n'
        '    assert content_type(".config.yaml") == "application/x-yaml"\n'
        '    assert content_type(".backup.csv") == "text/csv"\n'),
    "bug_report": ("The analytics team's CSV exports open garbled in Excel for some users but not "
                   "others, an embedded image on the docs site intermittently renders as raw text, "
                   "and a build-pipeline config artifact was displayed inline by the browser "
                   "instead of downloading. A failing repro is at tests/test_regression.py. Fix "
                   "content_type so served assets get the intended types, without breaking "
                   "existing behaviour."),
}


TRAPS_HARD_G = {t["name"]: t for t in [HOSTALLOW, MIMEMAP]}
