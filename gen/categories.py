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
}

CATEGORIES = sorted(set(CATEGORY.values()))
