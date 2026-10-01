"""E8 (D43): the LLM adversary's plan is enforced by the environment; its message takes the normal path."""
import json

import pytest

from obt import config
from obt.agent import ScriptedClaimBuyer
from obt.attacks import llm_adversary as adv
from obt.attacks.suppliers import make_supplier, scenario_name
from obt.env.beer_game import MAIN, GameConfig, OrderRequest
from obt.extractor import RuleExtractor
from obt.llm import LLM
from obt.sim import Sim, SimConfig

G = GameConfig(rounds=8)


def fake(replies):
    """An attacker LLM answering from a list (or a function of the observation)."""
    seen = []

    def answer(system, user):
        seen.append((system, json.loads(user)))
        r = replies(len(seen), json.loads(user)) if callable(replies) else replies[min(len(seen), len(replies)) - 1]
        return r if isinstance(r, str) else json.dumps(r)
    return LLM("fake", "fake-attacker", fake=answer), seen


def reply(msg="", qty=0, at=99, price=5.0, new=False):
    return {"message": msg, "plan": {"deliver_qty": qty, "deliver_round": at, "invoice_unit_price": price},
            "new_identity": new}


def test_prompts_are_frozen():
    assert adv.prompt_sha256("black") == config.ATTACKER_BLACKBOX_SHA256
    assert adv.prompt_sha256("white") == config.ATTACKER_WHITEBOX_SHA256
    assert "B(c)" not in adv.system_prompt("black", "obt") and "B(c)" in adv.system_prompt("white", "obt")
    assert "reputation" in adv.system_prompt("white", "rep-strict") and set(adv.DEFENSES) == {
        "none", "provenance", "llm_selfcheck", "rep-strict", "rep-n18", "obt", "obt+planner"}


def test_the_plan_decides_what_ships_and_what_is_invoiced():
    llm, _ = fake([reply("20 widgets by round 3 at $4.50", qty=12, at=1, price=7.25)])
    a = adv.LLMAdversary(G, 1, llm)
    assert a.offer_message(1, 20) == "20 widgets by round 3 at $4.50"
    r1 = a.on_order(OrderRequest("o1", 1, 8))
    r2 = a.on_order(OrderRequest("o2", 1, 10))           # same round: shares the plan's 12 units
    assert r1.unit_price == r2.unit_price == 7.25
    assert r1.shipments == ((8, 3),) and r2.shipments == ((4, 3),)   # arrival clamped to round + main lead (2)


def test_identities_switch_at_most_twice_and_unparseable_output_falls_back_to_honest():
    llm, _ = fake([reply(new=True), reply(new=True), reply(new=True), "not json"])
    a = adv.LLMAdversary(G, 1, llm)
    ids = []
    for t in (1, 2, 3):
        a.offer_message(t, 20)
        ids.append(a.identity)
    assert ids == ["S_main_2", "S_main_3", "S_main_3"] and a.report()["identity_switches"] == 2
    assert a.offer_message(4, 20) is None and a.fallbacks == 1
    assert a.on_order(OrderRequest("o9", 4, 6)).shipments == ((6, 6),)     # honest fallback: ships on time at $5
    assert a.rounds[-1]["fallback"]


def test_only_the_white_box_attacker_sees_the_buyer_trust_state():
    for knowledge, sees in (("black", False), ("white", True)):
        llm, seen = fake([reply("hello")] * 8)
        main = adv.LLMAdversary(G, 1, llm, knowledge, "obt")
        sim = Sim(SimConfig(game=G, defense="obt", transport="inproc"), 1, main, ScriptedClaimBuyer(G),
                  extractor=RuleExtractor())
        sim.run()
        obs = seen[0][1]
        assert ("buyer_trust_state" in obs) is sees
        if sees:
            assert obs["buyer_trust_state"]["B"] == pytest.approx(5.0) and obs["buyer_trust_state"]["P"] == 0.0


def test_end_to_end_obt_blocks_the_lie_and_no_defense_pays_for_it():
    # Offers 20 widgets by round t+2 at $5.00 every round, ships nothing and invoices $6.
    def lie(n, o):
        return reply(f"We will have 20 widgets delivered by round {o['round'] + 2}. Unit price $5.00, valid until "
                     f"round {o['round'] + 2}.", qty=0, price=6.0)
    assert scenario_name(13) == "13_llm_adversary_blackbox" and scenario_name(14) == "14_llm_adversary_whitebox"
    paid = {}
    for defense in ("obt", "none"):
        llm, _ = fake(lie)
        main = make_supplier(13, G, 1, defense=defense, attacker_llm=llm)
        sim = Sim(SimConfig(game=G, defense=defense, transport="inproc"), 1, main, ScriptedClaimBuyer(G),
                  extractor=RuleExtractor())
        res = sim.run()
        rep = main.report()
        assert res.metrics["invariant_violations"]["count"] == 0 and res.metrics["loss_bound"]["ok"] is not False
        assert rep["prompt_sha256"] == config.ATTACKER_BLACKBOX_SHA256 and len(rep["rounds"]) == G.rounds
        assert all(o["shipments"] == [] for r in rep["rounds"] for o in r["orders"])     # never ships
        paid[defense] = sum(p["amount"] for p in rep["payments"])
        if defense == "obt":
            blocked = [a for t in res.trace for a in t["actions"] if a[0] == "ORDER" and a[1] == MAIN]
            assert blocked and all(a[4] == "BLOCKED" and a[5] == "OVER_BUDGET" for a in blocked)
    assert paid["obt"] == 0 and paid["none"] > 0          # OBT never pays for the lie; no defense does
