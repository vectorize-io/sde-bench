"""HARD-tier trap batch B for the sdebench generator.

Same schema as gen/traps.py (see its module docstring), plus a `category` key per trap
(values drawn from gen/categories.py CATEGORIES; wire into CATEGORY when emitting):
  redact -> filter-rule, retryjitter -> set-membership, csvquote -> invariant.

Hard-tier design goals: multi-part policies with a counter-intuitive carve-out, WIDE hidden
tests (each policy component pinned by a separate test function), and bug reports written in
symptom vocabulary far from the decision wording.
"""


# --------------------------------------------------------------------------- redact

def _redact_mod(suffixes, card_tail, doc=""):
    if card_tail:
        branch = ('            if norm.endswith("card_number"):\n'
                  '                out[key] = "***" + str(value)[-4:]\n'
                  '            elif any(norm.endswith(s) for s in _SENSITIVE_SUFFIXES):\n')
    else:
        branch = '            if any(norm.endswith(s) for s in _SENSITIVE_SUFFIXES):\n'
    return ('"""Redact sensitive fields from log events."""\nimport re\n\n'
            f'_SENSITIVE_SUFFIXES = {suffixes!r}\n\n\n'
            'def _norm(key):\n'
            '    # normalize a key: lowercase, runs of non-alphanumerics -> underscore\n'
            '    return re.sub(r"[^a-z0-9]+", "_", str(key).lower())\n\n\n'
            f'def redact(event):\n    """Recursively mask sensitive fields in a log event.{doc}"""\n'
            '    if isinstance(event, dict):\n'
            '        out = {}\n'
            '        for key, value in event.items():\n'
            '            norm = _norm(key)\n'
            + branch +
            '                out[key] = "***"\n'
            '            else:\n'
            '                out[key] = redact(value)\n'
            '        return out\n'
            '    if isinstance(event, list):\n'
            '        return [redact(item) for item in event]\n'
            '    return event\n')


REDACT = {
    "name": "redact",
    "marker": "last4",   # the answer-token used by the source-isolation check
    "category": "filter-rule",
    "pkg": "logsafe",
    "module": "logsafe/redact.py",
    "init": '"""logsafe package."""\nfrom .redact import redact\n\n__all__ = ["redact"]\n',
    "import_line": "from logsafe import redact",
    # HEAD bug: exact top-level match on two names only; no recursion, no suffixes
    "bug": ('"""Redact sensitive fields from log events."""\n\n\n'
            'def redact(event):\n'
            '    """Mask sensitive fields in a log event."""\n'
            '    out = dict(event)\n'
            '    for key in ("password", "token"):\n'
            '        if key in out:\n'
            '            out[key] = "***"\n'
            '    return out\n'),
    "correct": _redact_mod(
        ("password", "token", "api_key", "ssn", "card_number"), card_tail=True,
        doc=("\n\n    A key is sensitive when its normalized name (lowercase, non-alphanumerics\n"
             "    to underscores) ENDS WITH one of _SENSITIVE_SUFFIXES. Sensitive values become\n"
             '    "***", except card numbers, which keep their last 4 digits ("***1234") so\n'
             "    support can reconcile disputes. Email is deliberately NOT sensitive - support\n"
             "    answers tickets by email.\n    ")),
    "naive": [
        # suffix match, but masks email too AND fully masks card numbers
        _redact_mod(("password", "token", "api_key", "ssn", "card_number", "email"), card_tail=False),
        # suffix match, keeps card tail, but masks email too
        _redact_mod(("password", "token", "api_key", "ssn", "card_number", "email"), card_tail=True),
    ],
    "decision_subject": "fix: close the gaps in log-event scrubbing flagged by the compliance audit",
    "decision_rationale": (
        "The audit found secrets leaking through redact - it only matched two exact top-level names. "
        "New rule: normalize each key (lowercase, non-alphanumerics to underscores) and treat it as "
        "sensitive when it ENDS WITH password, token, api_key, ssn or card_number, recursively through "
        "nested dicts and lists. Sensitive values become ***, except card numbers, which keep their "
        "last4 as ***1234 - support reconciles chargeback disputes by the last4. Email is explicitly "
        "NOT masked: support answers tickets by looking customers up by email, and scrubbing it broke "
        "that once before."),
    "conversation": [
        {"role": "user", "text": "The compliance audit flagged that our log events ship secrets in plain text — a nested request payload with a user_password went straight to the aggregator, readable."},
        {"role": "assistant", "text": "I'll extend redact to walk nested dicts and lists and mask any key whose name contains a sensitive word — password, token, api_key, ssn, card_number, email — replacing the value with '***'."},
        {"role": "user", "text": "Two corrections. First, do NOT mask email — support answers tickets by looking customers up by email, and the last time someone scrubbed it we couldn't answer tickets for a week. Second, 'contains' is too broad; match on how the key ends."},
        {"role": "assistant", "text": "OK — suffix match, so user_password and session_token still hit. Should I lowercase keys before matching? We see header-style keys like X-Api-Key in these events."},
        {"role": "user", "text": "Yes — normalize the key first: lowercase it and turn every run of non-alphanumerics into an underscore, so X-Api-Key becomes x_api_key and matches the api_key suffix. One more thing about card numbers: support reconciles chargeback disputes by the tail digits, so a full mask breaks them."},
        {"role": "assistant", "text": "How much of the card number should survive redaction?"},
        {"role": "user", "text": "The last 4 digits. Write it as *** plus the last4, like ***1234. Everything else sensitive is a plain ***."},
        {"role": "assistant", "text": "Final rule: normalize the key (lowercase, non-alnum -> underscore); sensitive if it ends with password, token, api_key, ssn, or card_number; value becomes '***', except card_number which keeps its last4 as '***1234'; email is never masked; applied recursively through nested dicts and lists."},
    ],
    "existing_test": ('from logsafe import redact\n\n\n'
                      'def test_masks_password():\n'
                      '    out = redact({"password": "hunter2", "user": "bob"})\n'
                      '    assert out["password"] == "***"\n'
                      '    assert out["user"] == "bob"\n\n\n'
                      'def test_masks_token():\n'
                      '    out = redact({"token": "abc", "n": 1})\n'
                      '    assert out["token"] == "***"\n'
                      '    assert out["n"] == 1\n'),
    "repro_test": ('from logsafe import redact\n\n\n'
                   'def test_nested_secrets_masked():\n'
                   '    out = redact({"request": {"user_password": "x", "api_key": "k"}, "id": 7})\n'
                   '    assert out["request"]["user_password"] == "***"\n'
                   '    assert out["request"]["api_key"] == "***"\n'
                   '    assert out["id"] == 7\n'),
    "hidden_test": ('from logsafe import redact\n\n\n'
                    'def test_card_number_keeps_tail():\n'
                    '    out = redact({"card_number": "4111111111111234"})\n'
                    '    assert out["card_number"] == "***1234"\n\n\n'
                    'def test_card_number_suffix_nested():\n'
                    '    out = redact({"payment": {"customer_card_number": "5555444433331111"}})\n'
                    '    assert out["payment"]["customer_card_number"] == "***1111"\n\n\n'
                    'def test_email_not_masked():\n'
                    '    out = redact({"email": "a@b.com", "user": {"contact_email": "c@d.com"}})\n'
                    '    assert out["email"] == "a@b.com"\n'
                    '    assert out["user"]["contact_email"] == "c@d.com"\n\n\n'
                    'def test_suffix_and_normalization():\n'
                    '    out = redact({"X-Api-Key": "k", "user_ssn": "123-45-6789", "auth_token": "t"})\n'
                    '    assert out["X-Api-Key"] == "***"\n'
                    '    assert out["user_ssn"] == "***"\n'
                    '    assert out["auth_token"] == "***"\n\n\n'
                    'def test_recurses_lists():\n'
                    '    out = redact({"events": [{"password": "x", "id": 3}]})\n'
                    '    assert out["events"][0]["password"] == "***"\n'
                    '    assert out["events"][0]["id"] == 3\n\n\n'
                    'def test_non_sensitive_untouched():\n'
                    '    assert redact({"name": "bob", "meta": {"count": 2}}) == {"name": "bob", "meta": {"count": 2}}\n'),
    "bug_report": ("Customer secrets are showing up readable in the log pipeline - a nested request "
                   "payload reached the aggregator with its user_password and api_key values in plain "
                   "text. Only a couple of top-level fields ever get scrubbed. A failing repro is at "
                   "tests/test_regression.py. Fix redact so secrets stop leaking into logs, without "
                   "breaking existing behaviour."),
}


# --------------------------------------------------------------------------- retryjitter

def _retryj_mod(body, cap, cap_comment=""):
    return ('"""HTTP retry policy."""\n' + body +
            f'\n\ndef backoff_cap():\n{cap_comment}    return {cap}\n')


RETRYJITTER = {
    "name": "retryjitter",
    "marker": "429",   # the answer-token used by the source-isolation check
    "category": "set-membership",
    "pkg": "httpretry",
    "module": "httpretry/policy.py",
    "init": ('"""httpretry package."""\nfrom .policy import should_retry, backoff_cap\n\n'
             '__all__ = ["should_retry", "backoff_cap"]\n'),
    "import_line": "from httpretry import should_retry, backoff_cap",
    # HEAD bug: retries EVERY error status >= 400
    "bug": _retryj_mod(('\n\ndef should_retry(status, attempt):\n'
                        '    """Decide whether a failed request should be retried."""\n'
                        '    if attempt >= 4:\n'
                        '        return False\n'
                        '    return status >= 400\n'), 30),
    "correct": _retryj_mod(
        ('\n_RETRYABLE_4XX = frozenset({429, 408})   # ONLY these client codes are transient for us\n'
         '_MAX_ATTEMPTS = 4\n\n\n'
         'def should_retry(status, attempt):\n'
         '    """Retry any 5xx, plus exactly 429/408 from 4xx; never other 4xx; max 4 attempts."""\n'
         '    if attempt >= _MAX_ATTEMPTS:\n'
         '        return False\n'
         '    if 500 <= status <= 599:\n'
         '        return True\n'
         '    return status in _RETRYABLE_4XX\n'), 30,
        '    # 30s: the gateway LB kills idle connections at 32s; sleeping past 30 burns a dead conn\n'),
    "naive": [
        # only 5xx is retryable (drops the transient 4xx codes)
        _retryj_mod(('\n\ndef should_retry(status, attempt):\n'
                     '    """Decide whether a failed request should be retried."""\n'
                     '    if attempt >= 4:\n'
                     '        return False\n'
                     '    return 500 <= status <= 599\n'), 30),
        # 5xx + rate-limited, but misses request-timeout and doubles the cap
        _retryj_mod(('from http import HTTPStatus\n\n\n'
                     'def should_retry(status, attempt):\n'
                     '    """Decide whether a failed request should be retried."""\n'
                     '    if attempt >= 4:\n'
                     '        return False\n'
                     '    if 500 <= status <= 599:\n'
                     '        return True\n'
                     '    return status == HTTPStatus.TOO_MANY_REQUESTS\n'), 60),
    ],
    "decision_subject": "fix: stop the HTTP client from retrying non-transient failures",
    "decision_rationale": (
        "During the incident the client retried every failed request, including 401s, and locked "
        "accounts. Policy: retry any 5xx, plus exactly 429 and 408 from the 4xx range - 429 because "
        "the upstream rate-limits in bursts and 408 because their edge times requests out; every other "
        "4xx is permanent and must not be retried. At most 4 attempts total, and backoff sleeps cap at "
        "30 seconds because the gateway LB kills idle connections at 32s - sleeping longer just burns "
        "a dead connection."),
    "conversation": [
        {"role": "user", "text": "During last night's incident we hammered our own auth service — the HTTP client kept retrying a request that failed with 401 over and over until accounts locked out."},
        {"role": "assistant", "text": "I'll restrict retries to 5xx server errors only — every 4xx is treated as a permanent failure and never retried."},
        {"role": "user", "text": "Too strict. There are exactly two 4xx codes we MUST keep retrying: 429, because the upstream rate-limits in bursts and backs off fine, and 408, request timeouts at their edge. Everything else in 4xx is permanent."},
        {"role": "assistant", "text": "Got it — retry any 5xx plus exactly {429, 408}, nothing else below 500. Should attempts stay unlimited with exponential backoff?"},
        {"role": "user", "text": "No — cap the whole thing at 4 attempts total. Past that we page a human instead."},
        {"role": "assistant", "text": "And the backoff ceiling — keep the old client's 60 seconds?"},
        {"role": "user", "text": "No, 30 seconds. The gateway load balancer kills idle connections at 32s, so any sleep past 30 just resumes onto a dead connection."},
        {"role": "assistant", "text": "Final policy: retry any 5xx and exactly 429/408 from 4xx; never any other 4xx; at most 4 attempts; backoff capped at 30 seconds."},
    ],
    "existing_test": ('from httpretry import should_retry, backoff_cap\n\n\n'
                      'def test_server_errors_retryable():\n'
                      '    assert should_retry(500, 1) is True\n'
                      '    assert should_retry(503, 1) is True\n\n\n'
                      'def test_success_not_retried():\n'
                      '    assert should_retry(200, 1) is False\n'
                      '    assert backoff_cap() > 0\n'),
    "repro_test": ('from httpretry import should_retry\n\n\n'
                   'def test_auth_failure_not_retried():\n'
                   '    assert should_retry(401, 1) is False\n'
                   '    assert should_retry(503, 1) is True\n'),
    "hidden_test": ('from httpretry import should_retry, backoff_cap\n\n\n'
                    'def test_transient_4xx_retryable():\n'
                    '    assert should_retry(429, 1) is True\n'
                    '    assert should_retry(408, 1) is True\n\n\n'
                    'def test_permanent_4xx_not_retried():\n'
                    '    assert should_retry(400, 1) is False\n'
                    '    assert should_retry(401, 1) is False\n'
                    '    assert should_retry(403, 1) is False\n'
                    '    assert should_retry(404, 1) is False\n\n\n'
                    'def test_5xx_retryable():\n'
                    '    assert should_retry(500, 1) is True\n'
                    '    assert should_retry(503, 2) is True\n'
                    '    assert should_retry(599, 1) is True\n\n\n'
                    'def test_non_error_not_retried():\n'
                    '    assert should_retry(200, 1) is False\n'
                    '    assert should_retry(302, 1) is False\n\n\n'
                    'def test_attempt_budget():\n'
                    '    assert should_retry(503, 3) is True\n'
                    '    assert should_retry(503, 4) is False\n'
                    '    assert should_retry(429, 4) is False\n\n\n'
                    'def test_backoff_ceiling():\n'
                    '    assert backoff_cap() == 30\n'),
    "bug_report": ("Our auth service got hammered after a bad deploy - the HTTP client kept retrying "
                   "calls that had failed with 401 Unauthorized, repeating the same doomed request "
                   "until accounts locked out. Retrying cannot help a request the server has "
                   "definitively refused. A failing repro is at tests/test_regression.py. Fix the "
                   "retry decision without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- csvquote

_CSV_QUOTE_HELPER = ('def _field(value):\n'
                     '    text = str(value) if value is not None else str()\n')

_CSV_MINQUOTE = ("    if any(ch in text for ch in ',\"\\r\\n'):\n"
                 "        return '\"' + text.replace('\"', '\"\"') + '\"'\n"
                 "    return text\n")

_CSV_BODY = ('\n\ndef to_csv(rows, columns):\n'
             '    """Render rows (list of dicts) as CSV text for the ERP import."""\n'
             '    lines = [",".join(_field(col) for col in columns)]\n'
             '    for row in rows:\n'
             '        lines.append(",".join(_field(row.get(col)) for col in columns))\n'
             '    return "\\r\\n".join(lines) + "\\r\\n"\n')


CSVQUOTE = {
    "name": "csvquote",
    "marker": '="',   # the answer-token used by the source-isolation check
    "category": "invariant",
    "pkg": "erpexport",
    "module": "erpexport/writer.py",
    "init": '"""erpexport package."""\nfrom .writer import to_csv\n\n__all__ = ["to_csv"]\n',
    "import_line": "from erpexport import to_csv",
    # HEAD bug: plain comma join, no quoting, bare newlines
    "bug": ('"""CSV writer for the ERP import."""\n\n\n'
            'def to_csv(rows, columns):\n'
            '    """Render rows (list of dicts) as CSV text for the ERP import."""\n'
            '    lines = [",".join(columns)]\n'
            '    for row in rows:\n'
            '        lines.append(",".join(str(row.get(col)) if row.get(col) is not None else str() for col in columns))\n'
            '    return "\\n".join(lines) + "\\n"\n'),
    "correct": ('"""CSV writer for the ERP import."""\n\n\n'
                + _CSV_QUOTE_HELPER +
                '    if text.isdigit() and text.startswith("0") and len(text) > 1:\n'
                "        # Excel-style text formula: the ERP import strips leading zeros otherwise;\n"
                "        # the invariant is that a round-trip preserves the string exactly\n"
                "        return '=\"' + text + '\"'\n"
                + _CSV_MINQUOTE + _CSV_BODY),
    "naive": [
        # csv.writer with QUOTE_ALL: everything quoted, CRLF, but leading zeros still stripped by the ERP
        ('"""CSV writer for the ERP import."""\nimport csv\nimport io\n\n\n'
         'def to_csv(rows, columns):\n'
         '    """Render rows (list of dicts) as CSV text for the ERP import."""\n'
         '    buf = io.StringIO()\n'
         '    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)\n'
         '    writer.writerow(columns)\n'
         '    for row in rows:\n'
         '        writer.writerow(str(row.get(col)) if row.get(col) is not None else str() for col in columns)\n'
         '    return buf.getvalue()\n'),
        # minimal quoting + CRLF, but no special treatment for leading-zero digit strings
        ('"""CSV writer for the ERP import."""\n\n\n'
         + _CSV_QUOTE_HELPER + _CSV_MINQUOTE + _CSV_BODY),
    ],
    "decision_subject": "fix: make the ERP CSV export round-trip every field value exactly",
    "decision_rationale": (
        'Part numbers with leading zeros were coming back stripped after the ERP import - "00042" '
        'became "42" and broke SKU lookups; plain quoting does not stop the coercion. Digit-only '
        'values with a leading zero are now written in the Excel-style text form ="00042", the only '
        "form the ERP import keeps verbatim. Everything else uses minimal quoting (quote a field only "
        "when it contains a comma, quote, or newline; double embedded quotes), and rows end with CRLF "
        "because the ERP parser rejects bare newlines. Invariant: the import round-trips every field "
        "byte-for-byte."),
    "conversation": [
        {"role": "user", "text": "The ERP import mangled our part numbers again — \"00042\" came in as \"42\" and the SKU lookups all broke."},
        {"role": "assistant", "text": "The importer is coercing digit fields to numbers. I'll switch the export to quote every field with standard CSV quotes — quoted values should be read as text."},
        {"role": "user", "text": "We tried exactly that last year — the ERP still coerces a quoted digit string to a number and strips the zeros. Ordinary quoting doesn't stop it."},
        {"role": "assistant", "text": "Then what form does the ERP actually keep verbatim?"},
        {"role": "user", "text": "Excel-style text formulas. A digit-only value with a leading zero has to be written as =\"00042\" — that's the only thing its parser imports byte-for-byte."},
        {"role": "assistant", "text": "Understood. Should I write every field in that formula form, to be safe?"},
        {"role": "user", "text": "No — only the leading-zero digit strings. Everything else is normal CSV with minimal quoting: quote a field only if it contains a comma, a quote, or a newline, and double any embedded quotes. And rows must end with \\r\\n — the ERP parser rejects bare \\n line endings."},
        {"role": "assistant", "text": "Final: digit-strings with a leading zero are written as =\"...\"; all other fields use minimal quoting with doubled embedded quotes; comma delimiter; CRLF row endings. Round-trip through the ERP preserves every value exactly."},
    ],
    "existing_test": ('from erpexport import to_csv\n\n\n'
                      'def test_basic_export():\n'
                      '    out = to_csv([{"name": "widget", "qty": "5"}], ["name", "qty"])\n'
                      '    lines = out.splitlines()\n'
                      '    assert "name" in lines[0] and "qty" in lines[0]\n'
                      '    assert "widget" in lines[1] and "5" in lines[1]\n'
                      '    assert lines[1].count(",") == 1\n'),
    "repro_test": ('import csv\n\nfrom erpexport import to_csv\n\n\n'
                   'def test_comma_value_stays_in_one_column():\n'
                   '    out = to_csv([{"desc": "bolt, hex", "qty": "5"}], ["desc", "qty"])\n'
                   '    rows = list(csv.reader(out.splitlines()))\n'
                   '    assert rows[1] == ["bolt, hex", "5"]\n'),
    "hidden_test": ('from erpexport import to_csv\n\n\n'
                    'def test_leading_zero_written_as_text_formula():\n'
                    '    out = to_csv([{"sku": "00042"}], ["sku"])\n'
                    '    assert \'="00042"\' in out\n\n\n'
                    'def test_leading_zero_row_layout():\n'
                    '    out = to_csv([{"lot": "0731", "qty": "12"}], ["lot", "qty"])\n'
                    '    assert out.split("\\r\\n")[1] == \'="0731",12\'\n\n\n'
                    'def test_crlf_line_endings():\n'
                    '    out = to_csv([{"a": "x"}], ["a"])\n'
                    '    assert out.endswith("\\r\\n")\n'
                    '    assert out.count("\\r\\n") == 2\n'
                    '    assert "\\n" not in out.replace("\\r\\n", "")\n\n\n'
                    'def test_embedded_quotes_doubled():\n'
                    '    out = to_csv([{"desc": \'say "hi"\'}], ["desc"])\n'
                    '    assert \'"say ""hi"""\' in out\n\n\n'
                    'def test_plain_number_stays_bare():\n'
                    '    out = to_csv([{"qty": "42"}], ["qty"])\n'
                    '    assert out.split("\\r\\n")[1] == "42"\n\n\n'
                    'def test_comma_field_minimally_quoted():\n'
                    '    out = to_csv([{"desc": "bolt, hex", "qty": "7"}], ["desc", "qty"])\n'
                    '    assert out.split("\\r\\n")[1] == \'"bolt, hex",7\'\n'),
    "bug_report": ("The nightly export to the ERP is corrupting rows - any product description "
                   "containing a comma spills into the next column and shifts everything after it. "
                   "A failing repro is at tests/test_regression.py. Fix the export so field values "
                   "arrive in the ERP intact, without breaking existing behaviour."),
}


TRAPS_HARD_B = {t["name"]: t for t in [REDACT, RETRYJITTER, CSVQUOTE]}
