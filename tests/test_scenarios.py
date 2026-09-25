import random
from functools import lru_cache

import pytest

from obt.agent import BackupOnlyBuyer, ScriptedClaimBuyer
from obt.attacks.suppliers import SCENARIOS, make_supplier, scenario_name
from obt.env.beer_game import MAIN, OFFER_PHRASINGS, GameConfig, offer_text
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
            assert row["P"] <= row["B"] + 1e-9


def test_rule_extractor_parses_every_honest_phrasing():
    ex = RuleExtractor()
    rng = random.Random(0)
    for i in range(len(OFFER_PHRASINGS) * 5):
        txt = offer_text(rng, 7, 13, 9, 5.0, 9)
        claims = ex.extract(Message(msg_hash=f"h{i}", counterparty=MAIN, round=7, text=txt))
        got = sorted((c.template, tuple(sorted(c.slots.items()))) for c in claims)
        assert got == [("DELIVERY", (("by_round", 9), ("item", "widget"), ("qty", 13))),
                       ("PRICE", (("item", "widget"), ("unit_price", 5.0), ("valid_until", 9)))], txt


def test_1_honest_earns_trust_and_never_fails():
    r = run(1)
    assert r.metrics["claims"]["FAILED"] == 0
    assert r.metrics["max_B"] > 10 * B0
    assert r.metrics["main_units_received"] == r.metrics["main_units_ordered"] or \
        r.metrics["claims"]["PENDING"] > 0  # last lot may still be in transit at the horizon


def test_2_always_lie_capped_at_b0():
    r = run(2)
    executed = [a for a in main_actions(r) if a[4] == "EXECUTED"]
    assert executed and all(a[3] <= B0 + 1e-9 for a in executed)
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


def test_8_claim_splitting_many_small_claims_one_big_order_blocked():
    r = run(8)
    late = [row for row in r.trace if row["round"] >= 20]
    assert all(sum(1 for c in row["offer"] if c[1] == "DELIVERY") >= 3 for row in late)
    blocked = [a for row in late for a in row["actions"] if a[0] == "ORDER" and a[1] == MAIN and a[4] == "BLOCKED"]
    # One order backed by several small DELIVERY claims (+ the quote) is still budgeted as one action.
    assert blocked and all(len(a[6]) >= 4 and a[5] == "OVER_BUDGET" for a in blocked)
    assert r.metrics["claims"]["FAILED"] == 0


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
