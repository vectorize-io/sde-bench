"""Canonical task taxonomy: the KIND of non-guessable decision each task's fix hinges on.

This is the dataset's `category` axis (orthogonal to source (history/conversation) and tier real-function/planted).
Single source of truth: the emitters write `category` into each task.json from CATEGORY, and the
structural validator checks every task's category is in CATEGORIES. Keyed by short task name
(the `boltons-<name>` suffix)."""

CATEGORY = {
    "slugify": "mapping",           # symbol/string -> word mapping
    "pluralize": "mapping",         # irregular singular -> plural mapping
    "under2camel": "set-membership",  # which tokens are in the acronym set
    "parseflag": "set-membership",  # which strings are in the truthy set
    "rounding": "numeric-policy",   # which rounding rule
    "budget": "numeric-policy",     # the exact numeric constant
    "discount": "ordering",         # the order operations are applied
    "listmerge": "collection-merge",  # how collections combine (union/dedup/order)
    "findhashtags": "filter-rule",  # a filter with a carve-out exception
    "omdset": "invariant",          # a data-structure invariant to preserve
    # hard tier (multi-part policies; see traps_hard_a/b.py)
    "dedupe": "collection-merge",   # dup key + conflict winner + tie-break
    "trimstats": "numeric-policy",  # drop exactly top-2 then nearest-rank p95
    "sched": "ordering",            # priority, runtime tie-break, tenant fairness
    "redact": "filter-rule",        # suffix-match set + card last4 + email carve-out
    "retryjitter": "set-membership",  # retryable statuses {5xx,429,408} + caps
    "csvquote": "invariant",        # leading-zero round-trip via ="..." + CRLF
    # hard tier batch C (see traps_hard_c.py)
    "slalog": "filter-rule",        # window merge + sub-minute blip carve-out + maintenance notice gate
    "unitparse": "mapping",         # suffix -> bytes mapping that depends on the resource kind
    # hard tier batch D (see traps_hard_d.py)
    "statetrans": "invariant",      # lifecycle transition map + lowercase canonical state
    "deploywave": "ordering",       # dependency leveling + tier-within-wave + canary wave 0
    # hard tier batch E (see traps_hard_e.py; buried-decision long conversations)
    "tagmerge": "collection-merge",  # precedence union + first-casing dedupe + scoped tombstones
    "seqledger": "invariant",       # consecutive seq + compaction stride 100 + hash-checked replays
    # hard tier batch F (see traps_hard_f.py; buried-decision long conversations)
    "overage": "numeric-policy",    # ceil-prorated quota + 25-unit grace + 50-unit blocks
    "drainplan": "ordering",        # in-flight shortest-first + idempotent-in-window + deadline drops
    # hard tier batch G (see traps_hard_g.py; buried-decision long conversations)
    "hostallow": "set-membership",  # lowercase-normalized exact set + single-label wildcards + exact-only IPs
    "mimemap": "mapping",           # pinned case-insensitive extension table + dotfile carve-out
    # hard tier batch I (see traps_hard_i.py; buried-decision long conversations)
    "cachekey": "filter-rule",      # tracking-drop set + utm_content carve-out + empty-value drop + surgical normalization
    "featflag": "invariant",        # pinned per-flag hash input + strict < boundary + corp-beta-only override
}

CATEGORIES = sorted(set(CATEGORY.values()))
