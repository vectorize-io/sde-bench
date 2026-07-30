"""HARD-tier trap batch D for the sdebench generator.

Same schema as gen/traps.py (see its module docstring). Categories (gen/categories.py):
  statetrans -> invariant   (order-lifecycle transition map + case canonicalization)
  deploywave -> ordering    (dependency leveling + tier order + canary wave)

Hard-tier design goals: multi-part policies (3+ interacting constraints, so one feedback round
reveals only part of the rule), bug reports written in symptom vocabulary far from the decision
wording, WIDE hidden tests (each policy component pinned by its own small test function), and
two naive guesses per trap, each passing the repro but failing hidden.
"""


# --------------------------------------------------------------------------- statetrans
# Policy (all parts required): allowed transition map --
#   pending -> {paid, on_hold, cancelled}; paid -> {shipped, on_hold} (a charged order can
#   NEVER move straight to cancelled - it must go on_hold first; decided after the
#   double-refund incident); on_hold -> {pending, cancelled}; shipped -> {returned};
#   returned -> {refunded} (refunded is reachable ONLY from returned, never straight from
#   paid/shipped); cancelled and refunded are terminal.
# Inputs (current state and target) compare case-insensitively; the stored state is always
# the lowercase canonical form.

_ST_RAISE = ('    if cur not in _ALLOWED or dst not in _ALLOWED[cur]:\n'
             '        raise InvalidTransition(str(order["state"]) + " -> " + str(target))\n')


def _st_mod(shipped_targets, cur_expr, dst_expr, doc=""):
    return ('"""Order lifecycle state machine."""\n\n\n'
            'class InvalidTransition(Exception):\n'
            '    """Raised when an order may not move to the requested state."""\n\n\n'
            '_ALLOWED = {\n'
            '    "pending": {"paid", "on_hold", "cancelled"},\n'
            '    "paid": {"shipped", "on_hold"},\n'
            '    "on_hold": {"pending", "cancelled"},\n'
            f'    "shipped": {shipped_targets},\n'
            '    "returned": {"refunded"},\n'
            '    "cancelled": set(),\n'
            '    "refunded": set(),\n'
            '}\n\n\n'
            'def advance(order, target):\n'
            f'    """Move an order to `target`, enforcing the lifecycle transition map.{doc}"""\n'
            f'    cur = {cur_expr}\n'
            f'    dst = {dst_expr}\n'
            + _ST_RAISE +
            '    order["state"] = dst\n'
            '    return order\n')


STATETRANS = {
    "name": "statetrans",
    "marker": "double-refund",   # the answer-token used by the source-isolation check
    "category": "invariant",
    "pkg": "orderflow",
    "module": "orderflow/transitions.py",
    "init": ('"""orderflow package."""\nfrom .transitions import advance, InvalidTransition\n\n'
             '__all__ = ["advance", "InvalidTransition"]\n'),
    "import_line": "from orderflow import advance, InvalidTransition",
    # HEAD bug: any "forward-looking" move along a linear progress order is allowed (so
    # paid->cancelled and shipped->refunded both pass), backwards moves like paid->on_hold
    # and on_hold->pending are refused, and matching is case-sensitive.
    "bug": ('"""Order lifecycle state machine."""\n\n\n'
            'class InvalidTransition(Exception):\n'
            '    """Raised when an order may not move to the requested state."""\n\n\n'
            '_ORDER = ["pending", "on_hold", "paid", "shipped", "returned", "cancelled", "refunded"]\n\n\n'
            'def advance(order, target):\n'
            '    """Move an order to `target`, refusing moves that go backwards."""\n'
            '    cur = order["state"]\n'
            '    if cur not in _ORDER or target not in _ORDER:\n'
            '        raise InvalidTransition(str(cur) + " -> " + str(target))\n'
            '    if _ORDER.index(target) <= _ORDER.index(cur):\n'
            '        raise InvalidTransition(str(cur) + " -> " + str(target))\n'
            '    order["state"] = target\n'
            '    return order\n'),
    "correct": _st_mod(
        '{"returned"}', 'str(order["state"]).lower()', 'str(target).lower()',
        doc=("\n\n    Lifecycle policy (pinned after the double-refund incident):\n"
             "      - pending -> paid | on_hold | cancelled\n"
             "      - paid    -> shipped | on_hold   (NEVER straight to cancelled: hold first)\n"
             "      - on_hold -> pending | cancelled\n"
             "      - shipped -> returned; returned -> refunded (the ONLY way into refunded)\n"
             "      - cancelled and refunded are terminal.\n"
             "    States compare case-insensitively; the stored state is always the lowercase\n"
             "    canonical form.\n    ")),
    "naive": [
        # blocks paid->cancelled but still allows shipped->refunded, and stays case-sensitive
        _st_mod('{"returned", "refunded"}', 'order["state"]', 'target'),
        # the full correct map, but normalizes the target only (current state stays case-sensitive)
        _st_mod('{"returned"}', 'order["state"]', 'str(target).lower()'),
    ],
    "decision_subject": "fix: pin the order lifecycle transition map after the double-refund incident",
    "decision_rationale": (
        "The double-refund incident happened because advance() let an order jump to any later-looking "
        "status: one order was cancelled while its charge was mid-capture and then refunded twice. The "
        "lifecycle is now pinned: pending -> paid/on_hold/cancelled; paid -> shipped/on_hold ONLY - a "
        "charged order can never move straight to cancelled, it must go on_hold first so the charge "
        "settles; on_hold -> pending/cancelled; shipped -> returned; returned -> refunded, and refunded "
        "is reachable ONLY from returned, never straight from paid or shipped; cancelled and refunded "
        "are terminal. The OMS sends states like 'Paid'/'SHIPPED', so advance compares states "
        "case-insensitively and always stores the lowercase canonical form."),
    "conversation": [
        {"role": "user", "text": "Finance flagged a reconciliation mess: two orders yesterday were charged and cancelled on the same day, and one of them ended up refunded twice. Meanwhile support says some orders just get stuck and they can't move them at all."},
        {"role": "assistant", "text": "advance() currently allows any forward-looking move, so a paid order can jump straight to cancelled. I'll block that one edge: once an order is paid, cancel is off the table."},
        {"role": "user", "text": "Blocking paid->cancelled is right, but it's not one edge - we pinned the whole lifecycle after the double-refund incident. From pending you can go to paid, on_hold, or cancelled. From paid, only to shipped or on_hold - a charged order has to be put on_hold first and cancelled from there, so the charge settles before anyone cancels."},
        {"role": "assistant", "text": "Got it. What about the back half of the lifecycle - shipped, returned, refunded?"},
        {"role": "user", "text": "shipped can only go to returned, and returned only to refunded. Refunded is reachable ONLY from returned - never straight from paid or shipped; that shortcut is exactly how the double refund happened. And cancelled and refunded are terminal, nothing ever moves out of them."},
        {"role": "assistant", "text": "Understood. And on_hold - does it go back to paid once the hold clears?"},
        {"role": "user", "text": "No - on_hold releases back to pending, or goes to cancelled. That's the stuck-order complaint, by the way: support parks an order on hold and then can't release it. One more thing: the OMS sends states like 'Paid' and 'SHIPPED' - compare case-insensitively, but whatever you store must be the lowercase canonical form."},
        {"role": "assistant", "text": "Final map: pending -> paid/on_hold/cancelled; paid -> shipped/on_hold only, never straight to cancelled; on_hold -> pending/cancelled; shipped -> returned; returned -> refunded, the only way into refunded; cancelled and refunded terminal. Inputs match case-insensitively and the stored state is always lowercase."},
    ],
    "existing_test": (
        'import pytest\nfrom orderflow import advance, InvalidTransition\n\n\n'
        'def test_happy_path_moves():\n'
        '    assert advance({"state": "pending"}, "paid")["state"] == "paid"\n'
        '    assert advance({"state": "paid"}, "shipped")["state"] == "shipped"\n'
        '    assert advance({"state": "shipped"}, "returned")["state"] == "returned"\n'
        '    assert advance({"state": "returned"}, "refunded")["state"] == "refunded"\n\n\n'
        'def test_cancelled_order_cannot_be_charged():\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "cancelled"}, "paid")\n\n\n'
        'def test_unknown_states_rejected():\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "archived"}, "paid")\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "pending"}, "archived")\n'),
    # paid->cancelled must raise (HEAD allows it) and paid->on_hold must work (HEAD refuses
    # it as a backwards move); every candidate policy agrees on both, only HEAD differs.
    "repro_test": (
        'import pytest\nfrom orderflow import advance, InvalidTransition\n\n\n'
        'def test_charged_order_cannot_go_straight_to_cancelled():\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "paid"}, "cancelled")\n\n\n'
        'def test_charged_order_can_be_parked_on_hold():\n'
        '    assert advance({"state": "paid"}, "on_hold")["state"] == "on_hold"\n'),
    "hidden_test": (
        'import pytest\nfrom orderflow import advance, InvalidTransition\n\n\n'
        'def test_cancel_reachable_only_from_pending_or_hold():\n'
        '    assert advance({"state": "pending"}, "cancelled")["state"] == "cancelled"\n'
        '    assert advance({"state": "on_hold"}, "cancelled")["state"] == "cancelled"\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "paid"}, "cancelled")\n\n\n'
        'def test_refund_reachable_only_from_returned():\n'
        '    assert advance({"state": "returned"}, "refunded")["state"] == "refunded"\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "shipped"}, "refunded")\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "paid"}, "refunded")\n\n\n'
        'def test_hold_releases_back_to_pending_not_paid():\n'
        '    assert advance({"state": "on_hold"}, "pending")["state"] == "pending"\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "on_hold"}, "paid")\n\n\n'
        'def test_returned_order_cannot_be_cancelled():\n'
        '    with pytest.raises(InvalidTransition):\n'
        '        advance({"state": "returned"}, "cancelled")\n\n\n'
        'def test_terminal_states_stay_terminal():\n'
        '    for terminal in ("cancelled", "refunded"):\n'
        '        for target in ("pending", "paid", "on_hold", "shipped", "returned",\n'
        '                       "cancelled", "refunded"):\n'
        '            if target == terminal:\n'
        '                continue\n'
        '            with pytest.raises(InvalidTransition):\n'
        '                advance({"state": terminal}, target)\n\n\n'
        'def test_current_state_matched_case_insensitively():\n'
        '    assert advance({"state": "PAID"}, "shipped")["state"] == "shipped"\n'
        '    assert advance({"state": "On_Hold"}, "pending")["state"] == "pending"\n\n\n'
        'def test_target_matched_case_insensitively_and_stored_lowercase():\n'
        '    assert advance({"state": "pending"}, "PAID")["state"] == "paid"\n'
        '    assert advance({"state": "Shipped"}, "Returned")["state"] == "returned"\n'),
    "bug_report": ("Finance reconciliation found orders that were both charged and cancelled on the "
                   "same day, and one order was refunded twice. Support separately reports orders "
                   "that look stuck - they can't move them out of their current status at all. A "
                   "failing repro is at tests/test_regression.py. Fix advance so orders stop landing "
                   "in impossible statuses, without breaking existing behaviour."),
}


# --------------------------------------------------------------------------- deploywave
# Policy (all parts required): services deploy in waves by dependency depth - a service goes
# in the wave AFTER the deepest of its dependencies (topological leveling). WITHIN a wave,
# order by criticality: tier ascending (tier 0 = most critical goes first), then name A-Z
# for determinism. Services marked canary: true are pulled out of the leveling entirely and
# form wave 0, ALWAYS first regardless of their dependencies (ops decision: canaries validate
# the release before anything else; their deps are assumed already live from the previous
# release), ordered by name. No canaries -> no empty leading wave.


def _dw_leveled(sort_key, doc=""):
    return ('"""Deployment wave planner for release rollouts."""\n\n\n'
            'def plan_waves(services):\n'
            f'    """Group services into ordered deployment waves (lists of service names).{doc}"""\n'
            '    canaries = sorted(s["name"] for s in services if s.get("canary"))\n'
            '    rest = [s for s in services if not s.get("canary")]\n'
            '    by_name = {s["name"]: s for s in rest}\n'
            '    depth = {}\n\n'
            '    def _depth(name):\n'
            '        if name not in depth:\n'
            '            deps = [d for d in by_name[name].get("deps", []) if d in by_name]\n'
            '            depth[name] = 1 + max((_depth(d) for d in deps), default=-1)\n'
            '        return depth[name]\n\n'
            '    for s in rest:\n'
            '        _depth(s["name"])\n'
            '    waves = [canaries] if canaries else []\n'
            '    for level in range(max(depth.values(), default=-1) + 1):\n'
            '        group = sorted((s for s in rest if depth[s["name"]] == level),\n'
            f'                       key={sort_key})\n'
            '        waves.append([s["name"] for s in group])\n'
            '    return waves\n')


DEPLOYWAVE = {
    "name": "deploywave",
    "marker": "already live",   # the answer-token used by the source-isolation check
    "category": "ordering",
    "pkg": "shipctl",
    "module": "shipctl/waves.py",
    "init": '"""shipctl package."""\nfrom .waves import plan_waves\n\n__all__ = ["plan_waves"]\n',
    "import_line": "from shipctl import plan_waves",
    # HEAD bug: one flat wave, everything ordered by name (no leveling, no canaries, no tiers)
    "bug": ('"""Deployment wave planner for release rollouts."""\n\n\n'
            'def plan_waves(services):\n'
            '    """Group services into ordered deployment waves (lists of service names)."""\n'
            '    if not services:\n'
            '        return []\n'
            '    return [sorted(s["name"] for s in services)]\n'),
    "correct": _dw_leveled(
        'lambda s: (s["tier"], s["name"])',
        doc=("\n\n    Wave policy (release-eng decision):\n"
             "      1. Services marked canary form wave 0, ALWAYS first, ordered by name -\n"
             "         their dependencies are assumed already live from the previous release.\n"
             "      2. Every other service deploys in the wave AFTER the deepest of its\n"
             "         dependencies (dependency leveling).\n"
             "      3. Within a wave: tier ascending (tier 0 = most critical goes first),\n"
             "         then name A-Z for determinism. No canaries -> no empty leading wave.\n    ")),
    "naive": [
        # correct topological leveling + name order, but no canary extraction and no tiers
        ('"""Deployment wave planner for release rollouts."""\n\n\n'
         'def plan_waves(services):\n'
         '    """Group services into dependency-ordered deployment waves."""\n'
         '    by_name = {s["name"]: s for s in services}\n'
         '    depth = {}\n\n'
         '    def _depth(name):\n'
         '        if name not in depth:\n'
         '            deps = [d for d in by_name[name].get("deps", []) if d in by_name]\n'
         '            depth[name] = 1 + max((_depth(d) for d in deps), default=-1)\n'
         '        return depth[name]\n\n'
         '    for s in services:\n'
         '        _depth(s["name"])\n'
         '    waves = []\n'
         '    for level in range(max(depth.values(), default=-1) + 1):\n'
         '        waves.append(sorted(n for n in depth if depth[n] == level))\n'
         '    return waves\n'),
        # leveling + canary wave 0, but within-wave order by name only (ignores tier)
        _dw_leveled('lambda s: s["name"]'),
    ],
    "decision_subject": "fix: stage plan_waves rollouts by dependency depth, tier, and the canary wave",
    "decision_rationale": (
        "A release started checkout's API before the cache it reads from had gone out, which caused "
        "the serving blip during rollout. plan_waves now levels services into waves by dependency "
        "depth - a service deploys in the wave AFTER the deepest of its dependencies. Within a wave "
        "the most critical services go first: tier ascending (tier 0 first), then name A-Z so the "
        "plan is deterministic. Services marked canary form wave 0 and always deploy first regardless "
        "of their dependencies - ops decision: canaries validate the release before anything else "
        "rolls, and their dependencies are assumed already live from the previous release; the canary "
        "wave is ordered by name, and with no canaries there is no empty leading wave."),
    "conversation": [
        {"role": "user", "text": "Yesterday's release order looked random again - the checkout blip is back, and a service went out before the thing it reads from had even started rolling."},
        {"role": "assistant", "text": "plan_waves just returns everything as one alphabetical batch. I'll switch it to topological waves: a service deploys in the wave after its dependencies, alphabetical within a wave."},
        {"role": "user", "text": "Leveling by dependency depth is right - and make it the DEEPEST dependency, a service waits for the last of its deps. But alphabetical inside a wave isn't enough. Every service has a tier field, 0 being the most critical - inside a wave the most critical go first, so tier ascending, and fall back to name A-Z only when tiers tie, so the plan stays deterministic."},
        {"role": "assistant", "text": "Understood - depth leveling across waves, tier then name within a wave. Anything else the planner needs to handle?"},
        {"role": "user", "text": "Yes, canaries. Any service marked canary: true doesn't participate in the leveling at all - they form their own wave at the very front, before everything else, whatever their dependencies say."},
        {"role": "assistant", "text": "Even when a canary depends on a service that deploys in a later wave? That inverts the dependency order for it."},
        {"role": "user", "text": "That's deliberate - ops decision. The canaries exist to validate the release before anything else rolls, and their dependencies are assumed already live from the previous release. Sort the canary wave by name. And when there are no canaries there's no empty wave at the front - the first leveled wave just goes first."},
        {"role": "assistant", "text": "Final plan: canaries (if any) form wave 0 ordered by name; every other service lands in the wave after its deepest dependency; within a wave, tier ascending - 0 first - then name A-Z."},
    ],
    "existing_test": (
        'from shipctl import plan_waves\n\n\n'
        'def test_empty_plan():\n'
        '    assert plan_waves([]) == []\n\n\n'
        'def test_single_service():\n'
        '    services = [{"name": "solo", "deps": [], "tier": 1, "canary": False}]\n'
        '    assert plan_waves(services) == [["solo"]]\n\n\n'
        'def test_independent_services_share_a_wave():\n'
        '    services = [{"name": "beta", "deps": [], "tier": 1, "canary": False},\n'
        '                {"name": "alpha", "deps": [], "tier": 1, "canary": False}]\n'
        '    assert plan_waves(services) == [["alpha", "beta"]]\n\n\n'
        'def test_every_service_deployed_exactly_once():\n'
        '    services = [{"name": "a", "deps": [], "tier": 1, "canary": False},\n'
        '                {"name": "b", "deps": [], "tier": 1, "canary": False},\n'
        '                {"name": "c", "deps": [], "tier": 1, "canary": False}]\n'
        '    waves = plan_waves(services)\n'
        '    assert sorted(n for w in waves for n in w) == ["a", "b", "c"]\n'),
    # equal tiers, no canaries: every candidate policy levels these three the same way; only
    # the HEAD bug (one flat wave) puts a dependent beside its dependency.
    "repro_test": (
        'from shipctl import plan_waves\n\n\n'
        'def test_dependency_deploys_before_dependent():\n'
        '    services = [{"name": "api", "deps": ["store"], "tier": 1, "canary": False},\n'
        '                {"name": "store", "deps": [], "tier": 1, "canary": False},\n'
        '                {"name": "web", "deps": ["api"], "tier": 1, "canary": False}]\n'
        '    waves = plan_waves(services)\n'
        '    pos = {n: i for i, wave in enumerate(waves) for n in wave}\n'
        '    assert pos["store"] < pos["api"] < pos["web"]\n'),
    "hidden_test": (
        'from shipctl import plan_waves\n\n\n'
        'def _svc(name, deps=(), tier=1, canary=False):\n'
        '    return {"name": name, "deps": list(deps), "tier": tier, "canary": canary}\n\n\n'
        'def test_wave_follows_the_deepest_dependency():\n'
        '    services = [_svc("base"), _svc("mid", deps=["base"]),\n'
        '                _svc("top", deps=["base", "mid"])]\n'
        '    assert plan_waves(services) == [["base"], ["mid"], ["top"]]\n\n\n'
        'def test_within_wave_most_critical_tier_first():\n'
        '    services = [_svc("alpha", tier=2), _svc("mango", tier=0), _svc("zebra", tier=1)]\n'
        '    assert plan_waves(services) == [["mango", "zebra", "alpha"]]\n\n\n'
        'def test_tier_tie_breaks_by_name():\n'
        '    services = [_svc("delta", tier=1), _svc("bravo", tier=1), _svc("echo", tier=0)]\n'
        '    assert plan_waves(services) == [["echo", "bravo", "delta"]]\n\n\n'
        'def test_canaries_deploy_first_despite_dependencies():\n'
        '    services = [_svc("core"), _svc("api", deps=["core"]),\n'
        '                _svc("zzz-probe", deps=["api"], tier=3, canary=True)]\n'
        '    assert plan_waves(services) == [["zzz-probe"], ["core"], ["api"]]\n\n\n'
        'def test_canary_wave_ordered_by_name():\n'
        '    services = [_svc("watch", canary=True), _svc("probe", canary=True), _svc("app")]\n'
        '    assert plan_waves(services) == [["probe", "watch"], ["app"]]\n\n\n'
        'def test_dependency_on_a_canary_counts_as_satisfied():\n'
        '    services = [_svc("edge", canary=True), _svc("api", deps=["edge"])]\n'
        '    assert plan_waves(services) == [["edge"], ["api"]]\n\n\n'
        'def test_no_canaries_means_no_leading_empty_wave():\n'
        '    services = [_svc("a"), _svc("b", deps=["a"])]\n'
        '    assert plan_waves(services) == [["a"], ["b"]]\n\n\n'
        'def test_full_release_plan():\n'
        '    services = [_svc("probe", deps=["gateway"], tier=3, canary=True),\n'
        '                _svc("core-db", tier=0),\n'
        '                _svc("cache", tier=1),\n'
        '                _svc("audit", tier=3),\n'
        '                _svc("gateway", deps=["core-db", "cache"], tier=0),\n'
        '                _svc("worker", deps=["cache"], tier=2),\n'
        '                _svc("portal", deps=["gateway"], tier=1)]\n'
        '    assert plan_waves(services) == [["probe"],\n'
        '                                    ["core-db", "cache", "audit"],\n'
        '                                    ["gateway", "worker"],\n'
        '                                    ["portal"]]\n'),
    "bug_report": ("The rollout order for yesterday's release looked random - a dependent service "
                   "went out before the thing it reads from, and the checkout blip during release is "
                   "back. A failing repro is at tests/test_regression.py. Fix plan_waves so a service "
                   "never rolls out ahead of what it depends on, without breaking existing behaviour."),
}


TRAPS_HARD_D = {t["name"]: t for t in [STATETRANS, DEPLOYWAVE]}
