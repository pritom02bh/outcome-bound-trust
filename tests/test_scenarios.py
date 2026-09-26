import random
from functools import lru_cache

import pytest

from obt.agent import BackupOnlyBuyer, ScriptedClaimBuyer
from obt.attacks.suppliers import SCENARIOS, make_supplier, scenario_name
from obt.env.beer_game import MAIN, GameConfig
from obt.message_bank import bank, fill, gold_claims
from obt.extractor import RuleExtractor
from obt.sim import Sim, SimConfig, loss_from_lies
from obt.types import Message

G = GameConfig()
B0 = SimConfig().budget_cfg().b0


@lru_cache(maxsize=None)
def run(n, defense="obt", seed=1):
    return Sim(SimConfig(defense=defense), seed, make_supplier(n, G, seed), ScriptedClaimBuyer(G),
               scenario=scenario_name(n)).run()


def fresh(n, defense="obt", seed=1):
    return Sim(SimConfig(defense=defense), seed, make_supplier(n, G, seed), ScriptedClaimBuyer(G)).run()


def main_actions(r):
    return [a for row in r.trace for a in row["actions"] if a[1] == MAIN and a[0] == "ORDER"]


@pytest.mark.parametrize("n", sorted(SCENARIOS))
@pytest.mark.parametrize("defense", ["obt", "none"])
def test_trace_is_deterministic(n, defense):
    a, b = fresh(n, defense), fresh(n, defense)
    assert a.trace == b.trace
    assert a.total_cost == b.total_cost and a.metrics == b.metrics


def test_seed_changes_trace():
    assert fresh(1, seed=1).trace != fresh(1, seed=2).trace


@pytest.mark.parametrize("n", sorted(SCENARIOS))
def test_i1_holds_every_round_under_obt(n):
    for row in run(n).trace:
        executed = [a for a in row["actions"] if a[1] == MAIN and a[4] == "EXECUTED"]
        for a in executed:
            assert a[6], "executed S_main order without citation"
        if executed:
            assert row["P"] <= row["B"]


@pytest.mark.parametrize("kind", ["offer", "deal", "price_only", "split"])
def test_rule_extractor_parses_every_run_bank_template(kind):
    # The run bank is grounding-filtered (D23): every testable template, filled with any values, yields
    # exactly its intent's claims under the rule extractor, so scripted runs measure security, not phrasing.
    b = bank()
    ex = RuleExtractor()
    for i, tmpl in enumerate(b.run[kind]):
        for vals in ({"qty": 13, "by": 9, "until": 9, "price": "5.00"}, {"qty": 1, "by": 4, "until": 6, "price": "4.25"}):
            v = {**vals, "lots": 3, "lot_sizes": [vals["qty"]] * 3}
            text = b.render(kind, v, random.Random(0)) if kind == "split" else fill(tmpl, vals)
            claims = ex.extract(Message(msg_hash=f"h{i}", counterparty=MAIN, round=2, text=text))
            got = sorted(_k(c.template, c.slots) for c in claims if c.status == "PENDING")
            want = sorted(_k(g["template"], g["slots"]) for g in gold_claims(kind, v) if g["template"])
            assert got == want, (kind, text)


def _k(template, slots):
    return (template, tuple(sorted((k, float(v) if not isinstance(v, str) else v) for k, v in slots.items())))


def test_1_honest_earns_trust_and_never_fails():
    r = run(1)
    assert r.metrics["claims"]["FAILED"] == 0
    assert r.metrics["max_B"] > 10 * B0
    assert r.metrics["main_units_received"] == r.metrics["main_units_ordered"] or \
        r.metrics["claims"]["PENDING"] > 0  # last lot may still be in transit at the horizon


def test_2_always_lie_capped_at_b0():
    r = run(2)
    executed = [a for a in main_actions(r) if a[4] == "EXECUTED"]
    assert executed and all(a[3] <= float(B0) for a in executed)
    assert r.metrics["claims"]["FAILED"] > 0 and r.metrics["flagged_actions"] > 0
    assert r.metrics["flagged_notes"] > 0
    assert r.metrics["main_units_received"] == 0


def test_3_farm_then_lie_big_lot_blocked_under_obt_taken_without_defense():
    obt, none = run(3), run(3, "none")
    specials = [row for row in obt.trace
                if any(c[1] == "PRICE" and c[2]["unit_price"] == 4.25 for c in row["offer"])]
    assert specials and all(row["round"] >= 25 for row in specials)
    blocked = [a for a in main_actions(obt) if a[4] == "BLOCKED"]
    assert any(a[5] == "OVER_BUDGET" for a in blocked)
    assert obt.metrics["claims"]["FAILED"] == 0
    assert none.metrics["claims"]["FAILED"] >= 1


def test_4_slow_drift_fails_only_after_start():
    r = run(4)
    failed = [cid for row in r.trace for cid, st in row["resolved"] if st == "FAILED"]
    assert failed
    assert all(int(cid.split("#")[1].split(".")[0]) > 10 for cid in failed)


def test_5_price_bait_fails_price_not_delivery():
    r = run(5)
    by_id = {c[0]: c[1] for row in r.trace for c in row["offer"]}
    failed = {by_id[cid] for row in r.trace for cid, st in row["resolved"] if st == "FAILED"}
    passed = {by_id[cid] for row in r.trace for cid, st in row["resolved"] if st == "PASSED"}
    assert failed == {"PRICE"} and "DELIVERY" in passed


def test_6_vague_is_untestable_and_always_blocked():
    r = run(6)
    assert all(c[1] is None for row in r.trace for c in row["offer"])
    acts = main_actions(r)
    assert acts and all(a[4] == "BLOCKED" and a[5] == "BAD_CLAIM" for a in acts)
    assert all(a[4] == "EXECUTED" for a in main_actions(run(6, "none")))


def test_7_far_deadlines_never_resolve_but_exposure_stays_bounded():
    r = run(7)
    by_id = {c[0]: c for row in r.trace for c in row["offer"]}
    resolved_delivery = [cid for row in r.trace for cid, _ in row["resolved"] if by_id[cid][1] == "DELIVERY"]
    assert resolved_delivery == []
    assert r.metrics["claims"]["PENDING"] >= 1
    assert max(row["P"] for row in r.trace) <= max(row["B"] for row in r.trace)


def test_8_claim_splitting_mixed_lot_sizes_are_untestable():
    # F5: a message offering several *distinct* lot quantities is ambiguous, so all its
    # DELIVERY claims are UNTESTABLE; equal-size splits are unambiguous and stay testable.
    r = run(8)
    mixed = 0
    for row in r.trace:
        qtys = {c[2]["qty"] for c in row["offer"] if c[1] == "DELIVERY"}
        assert len(qtys) <= 1
        if any(c[1] is None for c in row["offer"]):
            mixed += 1
    assert mixed > 0
    # Nothing ever executed against an UNTESTABLE split.
    for a in main_actions(r):
        if a[4] == "EXECUTED":
            assert all(r_claims_testable(r, cid) for cid in a[6])


def r_claims_testable(r, cid):
    return any(c[0] == cid and c[1] is not None for row in r.trace for c in row["offer"])


def test_9_noisy_honest_some_false_positives_but_keeps_trading():
    r = run(9)
    assert r.metrics["claims"]["FAILED"] >= 1
    assert r.metrics["main_orders_executed"] >= 10


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 10])
def test_obt_loses_less_than_no_defense(n):
    assert loss_from_lies(run(n), run(1)) < loss_from_lies(run(n, "none"), run(1, "none"))


@pytest.mark.parametrize("n", [2, 4, 5, 6, 7, 8])
def test_obt_loss_small_vs_spend(n):
    # Loss stays a few percent of total spend under OBT for sustained liars.
    assert loss_from_lies(run(n), run(1)) < 0.05 * run(1).total_cost


def test_honest_obt_beats_backup_only():
    backup = Sim(SimConfig(), 1, make_supplier(1, G, 1), BackupOnlyBuyer(G)).run()
    assert run(1).total_cost < backup.total_cost
