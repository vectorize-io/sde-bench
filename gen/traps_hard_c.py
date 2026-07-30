"""HARD-tier trap batch C for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). Hard-tier design goals as in
batches A/B: multi-part policies with a counter-intuitive carve-out, bug reports written
in symptom vocabulary far from the decision wording, and WIDE hidden tests (each policy
component pinned by a separate small test function) so a truncated pytest tail reveals
only part of the rule. Each naive guess passes the repro but fails hidden.

Categories (see gen/categories.py taxonomy):
  slalog    -> filter-rule   (window merge + sub-minute blip carve-out + maintenance notice gate)
  unitparse -> mapping       (suffix -> bytes mapping that depends on the resource kind)
"""


# --------------------------------------------------------------------------- slalog
# Policy (all three parts required):
#   (a) overlapping or adjacent (touching) incident windows MERGE before any time is
#       summed, so concurrent alerts never double-count;
#   (b) a MERGED outage shorter than 60 seconds is a monitoring blip and is ignored
#       entirely (the threshold applies to the merged window, not to raw incidents);
#   (c) maintenance reduces downtime ONLY when announced at least 24 hours before its
#       start (announced_at); short-notice maintenance still counts as downtime.
# HEAD bug: sums raw incident durations (double-counts overlaps, counts blips) and
# subtracts every maintenance overlap regardless of notice.

_SLA_MERGE = ('\n\ndef _merge(windows):\n'
              '    merged = []\n'
              '    for start, end in sorted(windows):\n'
              '        if merged and start <= merged[-1][1]:\n'
              '            merged[-1][1] = max(merged[-1][1], end)\n'
              '        else:\n'
              '            merged.append([start, end])\n'
              '    return merged\n')

_SLA_SUBTRACT_ALL = ('        for m in maintenance:\n'
                     '            lo = max(start, _t(m["start"]))\n'
                     '            hi = min(end, _t(m["end"]))\n'
                     '            span -= max((hi - lo).total_seconds(), 0.0)\n')


def _sla_mod(body, doc="", helpers=""):
    return ('"""SLA downtime accounting."""\n'
            'from datetime import datetime, timedelta\n\n\n'
            'def _t(s):\n'
            '    return datetime.fromisoformat(s)\n'
            + helpers +
            '\n\ndef downtime_minutes(incidents, maintenance):\n'
            f'    """Total SLA downtime in minutes for a billing period.{doc}"""\n'
            + body)


SLALOG = {
    "name": "slalog",
    "marker": "short-notice",   # the answer-token used by the source-isolation check
    "pkg": "slalog",
    "module": "slalog/uptime.py",
    "init": '"""slalog package."""\nfrom .uptime import downtime_minutes\n\n__all__ = ["downtime_minutes"]\n',
    "import_line": "from slalog import downtime_minutes",
    # HEAD bug: raw per-incident sums (overlaps double-count, blips count) minus ALL maintenance
    "bug": _sla_mod(
        '    total = 0.0\n'
        '    for inc in incidents:\n'
        '        start, end = _t(inc["start"]), _t(inc["end"])\n'
        '        span = (end - start).total_seconds()\n'
        + _SLA_SUBTRACT_ALL +
        '        total += span\n'
        '    return total / 60.0\n'),
    "correct": _sla_mod(
        '    windows = [(_t(i["start"]), _t(i["end"])) for i in incidents]\n'
        '    total = 0.0\n'
        '    for start, end in _merge(windows):\n'
        '        span = (end - start).total_seconds()\n'
        '        if span < 60:\n'
        '            continue\n'
        '        for m in maintenance:\n'
        '            if _t(m["start"]) - _t(m["announced_at"]) < timedelta(hours=24):\n'
        '                continue\n'
        '            lo = max(start, _t(m["start"]))\n'
        '            hi = min(end, _t(m["end"]))\n'
        '            span -= max((hi - lo).total_seconds(), 0.0)\n'
        '        total += span\n'
        '    return total / 60.0\n',
        doc=("\n\n    Accounting policy (SLA credit addendum):\n"
             "      1. Overlapping or touching incident windows merge before any time\n"
             "         is summed, so concurrent alerts never double-count an outage.\n"
             "      2. A merged outage shorter than 60 seconds is a monitoring blip\n"
             "         and counts for nothing (the threshold applies to the merged\n"
             "         window, not to individual raw incidents).\n"
             "      3. Maintenance is excluded from downtime only when announced at\n"
             "         least 24 hours before its start (announced_at); short-notice\n"
             "         maintenance still counts as downtime.\n    "),
        helpers=_SLA_MERGE),
    "naive": [
        # merges overlaps, but no blip rule and subtracts ALL maintenance
        _sla_mod(
            '    windows = [(_t(i["start"]), _t(i["end"])) for i in incidents]\n'
            '    total = 0.0\n'
            '    for start, end in _merge(windows):\n'
            '        span = (end - start).total_seconds()\n'
            + _SLA_SUBTRACT_ALL +
            '        total += span\n'
            '    return total / 60.0\n',
            helpers=_SLA_MERGE),
        # merge + blip rule, but subtracts ALL maintenance regardless of notice
        _sla_mod(
            '    windows = [(_t(i["start"]), _t(i["end"])) for i in incidents]\n'
            '    total = 0.0\n'
            '    for start, end in _merge(windows):\n'
            '        span = (end - start).total_seconds()\n'
            '        if span < 60:\n'
            '            continue\n'
            + _SLA_SUBTRACT_ALL +
            '        total += span\n'
            '    return total / 60.0\n',
            helpers=_SLA_MERGE),
    ],
    "decision_subject": "fix: align downtime_minutes with the SLA credit accounting addendum",
    "decision_rationale": ("Tenants were disputing uptime reports because downtime_minutes summed raw "
                           "alert windows. Per the SLA credit addendum: overlapping or touching incident "
                           "windows merge before summing so concurrent alerts never double-count; a "
                           "merged outage under 60 seconds is a monitoring blip and counts for nothing "
                           "(the threshold applies to the merged window, not per raw incident); and "
                           "maintenance reduces downtime only when announced at least 24 hours before "
                           "its start (announced_at) - short-notice maintenance still counts as "
                           "downtime, customers do not eat credits for surprise maintenance."),
    "conversation": [
        {"role": "user", "text": "A tenant is disputing their SLA credit - our monthly report says they had 99.7% uptime but their ops team swears the service met 99.9%, and their own monitoring backs them up. Our downtime number is inflated somehow."},
        {"role": "assistant", "text": "downtime_minutes sums every incident window independently, so when several alerts fire for the same outage the same minutes get counted two or three times. I'll merge overlapping incident windows before summing - and touching windows too, an alert that starts exactly when another ends is the same outage."},
        {"role": "user", "text": "Merging is right - overlapping or touching windows are one outage, counted once. But that alone won't reconcile us with their number: their monitor ignores sub-minute flaps, and per the SLA addendum our accounting is supposed to as well."},
        {"role": "assistant", "text": "So I should drop any incident shorter than 60 seconds before merging?"},
        {"role": "user", "text": "No - measure it after merging, not per raw incident. If the merged outage is under 60 seconds it's a monitoring blip and counts for nothing; but if two 40-second alerts chain into one 80-second outage, that outage is real and counts in full."},
        {"role": "assistant", "text": "Got it. And maintenance windows - should time inside a scheduled maintenance window be excluded from the downtime total?"},
        {"role": "user", "text": "Only when it was properly announced: there must be at least 24 hours between announced_at and the window start. Short-notice maintenance still counts as downtime - that's in the addendum too, customers don't eat SLA credits for surprise maintenance."},
        {"role": "assistant", "text": "Understood: merge overlapping or touching incident windows first; ignore a merged outage under 60 seconds; then subtract maintenance overlap only when announced_at precedes the window start by 24 hours or more - short-notice maintenance stays in the downtime total."},
    ],
    "existing_test": (
        'from slalog import downtime_minutes\n\n\n'
        'def test_single_outage():\n'
        '    inc = [{"start": "2024-06-03T09:00:00", "end": "2024-06-03T09:30:00"}]\n'
        '    assert downtime_minutes(inc, []) == 30.0\n\n\n'
        'def test_no_incidents():\n'
        '    assert downtime_minutes([], []) == 0.0\n'
        '    maint = [{"start": "2024-06-05T02:00:00", "end": "2024-06-05T03:00:00",\n'
        '              "announced_at": "2024-06-01T09:00:00"}]\n'
        '    assert downtime_minutes([], maint) == 0.0\n\n\n'
        'def test_disjoint_outages_sum():\n'
        '    inc = [{"start": "2024-06-03T10:00:00", "end": "2024-06-03T10:10:00"},\n'
        '           {"start": "2024-06-03T14:00:00", "end": "2024-06-03T14:20:00"}]\n'
        '    assert downtime_minutes(inc, []) == 30.0\n\n\n'
        'def test_planned_maintenance_excluded():\n'
        '    inc = [{"start": "2024-06-08T02:00:00", "end": "2024-06-08T03:00:00"}]\n'
        '    maint = [{"start": "2024-06-08T02:00:00", "end": "2024-06-08T03:00:00",\n'
        '              "announced_at": "2024-06-05T10:00:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 0.0\n'),
    # two overlapping alerts for one outage, no maintenance, merged span >= 60s: every
    # candidate policy merges to 45 minutes; only the HEAD bug double-counts (60).
    "repro_test": (
        'from slalog import downtime_minutes\n\n\n'
        'def test_concurrent_alerts_not_double_counted():\n'
        '    incidents = [{"start": "2024-06-10T10:00:00", "end": "2024-06-10T10:30:00"},\n'
        '                 {"start": "2024-06-10T10:15:00", "end": "2024-06-10T10:45:00"}]\n'
        '    assert downtime_minutes(incidents, []) == 45.0\n'),
    "hidden_test": (
        'from slalog import downtime_minutes\n\n\n'
        'def test_overlapping_windows_merge():\n'
        '    inc = [{"start": "2024-06-01T13:00:00", "end": "2024-06-01T13:40:00"},\n'
        '           {"start": "2024-06-01T13:20:00", "end": "2024-06-01T14:00:00"}]\n'
        '    assert downtime_minutes(inc, []) == 60.0\n\n\n'
        'def test_touching_windows_merge_into_one_outage():\n'
        '    inc = [{"start": "2024-06-02T09:00:00", "end": "2024-06-02T09:00:40"},\n'
        '           {"start": "2024-06-02T09:00:40", "end": "2024-06-02T09:02:00"}]\n'
        '    assert downtime_minutes(inc, []) == 2.0\n\n\n'
        'def test_sub_minute_blip_ignored():\n'
        '    inc = [{"start": "2024-06-03T10:00:00", "end": "2024-06-03T10:00:45"}]\n'
        '    assert downtime_minutes(inc, []) == 0.0\n\n\n'
        'def test_exactly_sixty_seconds_counts():\n'
        '    inc = [{"start": "2024-06-03T11:00:00", "end": "2024-06-03T11:01:00"}]\n'
        '    assert downtime_minutes(inc, []) == 1.0\n\n\n'
        'def test_blip_threshold_applies_to_merged_window():\n'
        '    inc = [{"start": "2024-06-04T10:00:00", "end": "2024-06-04T10:00:50"},\n'
        '           {"start": "2024-06-04T10:00:35", "end": "2024-06-04T10:01:30"}]\n'
        '    assert downtime_minutes(inc, []) == 1.5\n\n\n'
        'def test_late_announced_maintenance_still_counts():\n'
        '    inc = [{"start": "2024-06-05T02:00:00", "end": "2024-06-05T04:00:00"}]\n'
        '    maint = [{"start": "2024-06-05T02:30:00", "end": "2024-06-05T03:30:00",\n'
        '              "announced_at": "2024-06-05T00:30:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 120.0\n\n\n'
        'def test_well_announced_maintenance_excluded():\n'
        '    inc = [{"start": "2024-06-06T02:00:00", "end": "2024-06-06T04:00:00"}]\n'
        '    maint = [{"start": "2024-06-06T02:30:00", "end": "2024-06-06T03:30:00",\n'
        '              "announced_at": "2024-06-03T09:00:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 60.0\n\n\n'
        'def test_exactly_24h_notice_qualifies():\n'
        '    inc = [{"start": "2024-06-10T05:00:00", "end": "2024-06-10T06:00:00"}]\n'
        '    maint = [{"start": "2024-06-10T05:00:00", "end": "2024-06-10T06:00:00",\n'
        '              "announced_at": "2024-06-09T05:00:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 0.0\n\n\n'
        'def test_partial_maintenance_overlap():\n'
        '    inc = [{"start": "2024-06-11T01:00:00", "end": "2024-06-11T02:00:00"}]\n'
        '    maint = [{"start": "2024-06-11T01:30:00", "end": "2024-06-11T02:30:00",\n'
        '              "announced_at": "2024-06-08T12:00:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 30.0\n\n\n'
        'def test_maintenance_outside_incident_ignored():\n'
        '    inc = [{"start": "2024-06-12T10:00:00", "end": "2024-06-12T10:30:00"}]\n'
        '    maint = [{"start": "2024-06-12T11:00:00", "end": "2024-06-12T12:00:00",\n'
        '              "announced_at": "2024-06-09T09:00:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 30.0\n\n\n'
        'def test_full_month_scenario():\n'
        '    inc = [{"start": "2024-06-20T08:00:00", "end": "2024-06-20T08:30:00"},\n'
        '           {"start": "2024-06-20T08:20:00", "end": "2024-06-20T09:00:00"},\n'
        '           {"start": "2024-06-21T12:00:00", "end": "2024-06-21T12:00:20"}]\n'
        '    maint = [{"start": "2024-06-20T08:30:00", "end": "2024-06-20T09:00:00",\n'
        '              "announced_at": "2024-06-20T06:30:00"}]\n'
        '    assert downtime_minutes(inc, maint) == 60.0\n'),
    "bug_report": ("A tenant is disputing their monthly SLA report: our report says 99.7% uptime for "
                   "the period, but their ops team swears the service met 99.9% and their own "
                   "monitoring agrees. downtime_minutes is producing a bigger number than the outage "
                   "time the tenant actually experienced. A failing repro is at "
                   "tests/test_regression.py. Fix downtime_minutes so the report matches real "
                   "downtime, without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- unitparse
# Policy (kind-dependent unit mapping, all parts required):
#   - memory: suffixes are BINARY (K=1024, M=1024**2, G=1024**3, T=1024**4),
#     case-insensitive; a bare number means MiB.
#   - disk: suffixes are DECIMAL (M=1000**2, G=1000**3, T=1000**4), case-insensitive;
#     a bare number means GB; the 'K' suffix is REJECTED with a ValueError (the
#     provisioning vendor API has no kilobyte disk unit).
# HEAD bug: every suffix decimal for both kinds (K accepted everywhere) and bare
# numbers parsed as raw bytes.

def _units_mod(tables, body, doc=""):
    return ('"""Config quantity parsing for the provisioning pipeline."""\n\n'
            + tables +
            '\n\ndef parse_quantity(value, kind):\n'
            '    """Convert a config quantity like \'512M\' into bytes for the given\n'
            f'    resource kind ("memory" or "disk").{doc}"""\n'
            + body)


_UNITS_SUFFIX_BRANCH = ('    s = str(value).strip()\n'
                        '    if s and s[-1].isalpha():\n'
                        '        suffix = s[-1].upper()\n'
                        '        if suffix not in units:\n'
                        '            raise ValueError("invalid unit suffix for " + kind + ": " + s[-1])\n'
                        '        return int(s[:-1]) * units[suffix]\n')

UNITPARSE = {
    "name": "unitparse",
    "marker": "MiB",   # the answer-token used by the source-isolation check
    "pkg": "infraconf",
    "module": "infraconf/units.py",
    "init": '"""infraconf package."""\nfrom .units import parse_quantity\n\n__all__ = ["parse_quantity"]\n',
    "import_line": "from infraconf import parse_quantity",
    # HEAD bug: decimal suffixes for everything, bare numbers are raw bytes
    "bug": _units_mod(
        '_UNITS = {"K": 1000, "M": 1000 ** 2, "G": 1000 ** 3, "T": 1000 ** 4}\n',
        '    units = _UNITS\n'
        + _UNITS_SUFFIX_BRANCH +
        '    return int(s)\n'),
    "correct": _units_mod(
        '_MEMORY_UNITS = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}\n'
        '_DISK_UNITS = {"M": 1000 ** 2, "G": 1000 ** 3, "T": 1000 ** 4}\n',
        '    units = _MEMORY_UNITS if kind == "memory" else _DISK_UNITS\n'
        + _UNITS_SUFFIX_BRANCH +
        '    if kind == "memory":\n'
        '        return int(s) * 1024 ** 2\n'
        '    return int(s) * 1000 ** 3\n',
        doc=("\n\n    Unit policy (provisioning vendor API):\n"
             "      - memory: suffixes are binary (K=1024 .. T=1024**4), case-insensitive;\n"
             "        a bare number means MiB (what the legacy templates meant).\n"
             "      - disk: suffixes are decimal (M=1000**2 .. T=1000**4), case-insensitive;\n"
             "        a bare number means GB; 'K' is rejected with a ValueError - the\n"
             "        vendor API has no kilobyte disk unit, and guessing would\n"
             "        misprovision the volume.\n    ")),
    "naive": [
        # all suffixes binary for both kinds, bare numbers MiB for both, K everywhere
        _units_mod(
            '_UNITS = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}\n',
            '    units = _UNITS\n'
            + _UNITS_SUFFIX_BRANCH +
            '    return int(s) * 1024 ** 2\n'),
        # memory binary / disk decimal, but bare numbers raw bytes and K accepted everywhere
        _units_mod(
            '_MEMORY_UNITS = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}\n'
            '_DISK_UNITS = {"K": 1000, "M": 1000 ** 2, "G": 1000 ** 3, "T": 1000 ** 4}\n',
            '    units = _MEMORY_UNITS if kind == "memory" else _DISK_UNITS\n'
            + _UNITS_SUFFIX_BRANCH +
            '    return int(s)\n'),
    ],
    "decision_subject": "fix: parse_quantity unit semantics per the provisioning vendor API",
    "decision_rationale": ("Migrated configs were misprovisioning because parse_quantity treated every "
                           "suffix as decimal and bare numbers as raw bytes. Vendor API semantics: "
                           "memory suffixes are binary (K=1024, M=1024**2, G=1024**3, T=1024**4, "
                           "case-insensitive) and a bare memory number means MiB; disk suffixes are "
                           "decimal (G=1000**3) and a bare disk number means GB; 'K' is rejected for "
                           "disk with a ValueError - the vendor API has no kilobyte disk unit and a "
                           "silent guess would misprovision the volume."),
    "conversation": [
        {"role": "user", "text": "We rolled out the new config parser and pods started getting OOM-killed within minutes of deploy - containers come up with way less memory than their config asks for. Storage also says some volumes ended up a few percent smaller than expected."},
        {"role": "assistant", "text": "parse_quantity is reading every suffix as decimal - '2G' of memory becomes 2*10**9 bytes, short of the 2 GiB the container needs. I'll switch all suffixes to binary, 1024-based, like Kubernetes' Gi."},
        {"role": "user", "text": "Binary for memory only. The cgroup limits the vendor API sets are 1024-based, so '1G' - or '1g', casing must not matter - of memory means exactly 1024**3 bytes. But disk stays decimal: storage is billed and partitioned in decimal units, '1G' of disk is exactly 1000**3."},
        {"role": "assistant", "text": "Understood, the mapping depends on the resource kind. And a bare number with no suffix - raw bytes for both kinds?"},
        {"role": "user", "text": "No. A bare memory value means MiB - that's what all the legacy templates meant, so 256 is 256*1024**2 bytes. A bare disk value means GB, 1000**3 per unit."},
        {"role": "assistant", "text": "Should the 'K' suffix work for both kinds - 1024 for memory, 1000 for disk?"},
        {"role": "user", "text": "For memory yes, K or k is 1024. For disk reject it with a ValueError: the vendor's provisioning API has no kilobyte disk unit, and silently guessing a size would misprovision the volume."},
        {"role": "assistant", "text": "Confirmed: memory suffixes are binary and case-insensitive with bare values in MiB; disk suffixes are decimal with bare values in GB; 'K' is valid for memory only and raises a ValueError for disk."},
    ],
    "existing_test": (
        'import pytest\nfrom infraconf import parse_quantity\n\n\n'
        'def test_unknown_suffix_rejected():\n'
        '    with pytest.raises(ValueError):\n'
        '        parse_quantity("12X", "memory")\n'
        '    with pytest.raises(ValueError):\n'
        '        parse_quantity("12Q", "disk")\n\n\n'
        'def test_garbage_rejected():\n'
        '    with pytest.raises(ValueError):\n'
        '        parse_quantity("abc", "disk")\n'
        '    with pytest.raises(ValueError):\n'
        '        parse_quantity("", "memory")\n\n\n'
        'def test_zero_values():\n'
        '    assert parse_quantity("0M", "memory") == 0\n'
        '    assert parse_quantity("0G", "disk") == 0\n'
        '    assert parse_quantity("0", "disk") == 0\n\n\n'
        'def test_whitespace_tolerated():\n'
        '    assert parse_quantity(" 0M ", "memory") == 0\n'),
    # a memory limit with a suffix: correct and both naives agree it is binary;
    # only the HEAD bug (decimal everywhere) undersizes it.
    "repro_test": (
        'from infraconf import parse_quantity\n\n\n'
        'def test_container_memory_limit_full_size():\n'
        '    assert parse_quantity("2G", "memory") == 2 * 1024 ** 3\n'
        '    assert parse_quantity("512m", "memory") == 512 * 1024 ** 2\n'),
    "hidden_test": (
        'import pytest\nfrom infraconf import parse_quantity\n\n\n'
        'def test_memory_suffixes_are_binary():\n'
        '    assert parse_quantity("1K", "memory") == 1024\n'
        '    assert parse_quantity("1M", "memory") == 1024 ** 2\n'
        '    assert parse_quantity("1G", "memory") == 1024 ** 3\n'
        '    assert parse_quantity("1T", "memory") == 1024 ** 4\n\n\n'
        'def test_memory_suffix_case_insensitive():\n'
        '    assert parse_quantity("2g", "memory") == 2 * 1024 ** 3\n'
        '    assert parse_quantity("8k", "memory") == 8 * 1024\n\n\n'
        'def test_bare_memory_number():\n'
        '    assert parse_quantity("256", "memory") == 256 * 1024 ** 2\n'
        '    assert parse_quantity("1", "memory") == 1024 ** 2\n\n\n'
        'def test_disk_suffixes_are_decimal():\n'
        '    assert parse_quantity("1M", "disk") == 1000 ** 2\n'
        '    assert parse_quantity("1G", "disk") == 1000 ** 3\n'
        '    assert parse_quantity("1T", "disk") == 1000 ** 4\n\n\n'
        'def test_disk_suffix_case_insensitive():\n'
        '    assert parse_quantity("40g", "disk") == 40 * 1000 ** 3\n\n\n'
        'def test_bare_disk_number():\n'
        '    assert parse_quantity("2", "disk") == 2 * 1000 ** 3\n\n\n'
        'def test_disk_kilobyte_suffix_rejected():\n'
        '    with pytest.raises(ValueError):\n'
        '        parse_quantity("64K", "disk")\n'
        '    with pytest.raises(ValueError):\n'
        '        parse_quantity("64k", "disk")\n\n\n'
        'def test_memory_kilobyte_suffix_allowed():\n'
        '    assert parse_quantity("512K", "memory") == 512 * 1024\n\n\n'
        'def test_larger_values():\n'
        '    assert parse_quantity("16G", "memory") == 16 * 1024 ** 3\n'
        '    assert parse_quantity("750G", "disk") == 750 * 1000 ** 3\n'),
    "bug_report": ("Since we migrated configs to the new parser, pods are being OOM-killed right "
                   "after deploy - containers come up with less memory than their config asks for - "
                   "and disk quotas also look slightly off on some volumes. A failing repro is at "
                   "tests/test_regression.py. Fix parse_quantity so provisioned resources match the "
                   "configs, without breaking existing behaviour."),
}


TRAPS_HARD_C = {t["name"]: t for t in [SLALOG, UNITPARSE]}
